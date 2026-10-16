"""Atomic profile proposals. Pending files belong to the request, never the live profile."""
import json
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.core.audit import log_action
from apps.core.exceptions import BusinessRuleError
from . import documents as store
from .models import Horse, HorseDocument, ProfileChangeRequest
from .serializers import ChangeAttachmentSerializer, HorseWriteSerializer, PROFILE_FIELDS

COLUMNS = {Horse._meta.get_field(attr).db_column: attr for attr in PROFILE_FIELDS}


def scalar(value):
    return None if value is None else str(value)


def snapshot(horse):
    return {
        "OwnerID": horse.owner_id, "ClubID": horse.club_id,
        "RegistrationStatus": horse.registration_status,
        "Profile": {col: scalar(getattr(horse, attr)) for col, attr in COLUMNS.items()},
        "Documents": list(horse.documents.order_by("id").values(
            "id", "file_url", "document_name", "document_type", "uploaded_by_id",
            "is_visible_to_owner", "is_primary", "is_retired", "is_profile_image", "replaces_document_id")),
    }


def is_image(doc):
    return doc.is_profile_image and store.is_upload(doc.file_url) and store.content_type(doc.file_url).startswith("image/")


def document_info(doc):
    return {"DocumentID": doc.id, "DocumentName": doc.document_name,
            "DocumentType": doc.document_type, "IsUploadedFile": store.is_upload(doc.file_url),
            "FileUrl": f"/api/horse-documents/{doc.id}/file" if store.is_upload(doc.file_url) else doc.file_url}


def require_owner(horse, user):
    if horse.owner_id != user.pk or not user.has_perm("PROFILE_EDIT_REQUEST"):
        raise PermissionDenied("Chỉ chủ ngựa được gửi yêu cầu sửa lý lịch.")


def require_reviewer(horse, user):
    if horse.club_id != user.club_id or not user.has_perm("PROFILE_EDIT_APPROVE"):
        raise PermissionDenied("Bạn không được xử lý yêu cầu này.")


def require_approved(horse):
    if horse.registration_status != Horse.RegistrationStatus.APPROVED:
        raise BusinessRuleError("Chỉ yêu cầu cập nhật hồ sơ đã tiếp nhận.", "INVALID_STATUS")


def create(horse, user, changes, reason, evidence_document_id=None, *, files=None, **options):
    saved_files = []
    try:
        # Catch outside the transaction so every failed proposal removes its own staged files.
        with transaction.atomic():
            horse = Horse.objects.select_for_update().get(pk=horse.pk)
            require_owner(horse, user)
            require_approved(horse)
            pending = horse.profile_change_requests.filter(status="Pending").first()
            if pending:
                raise BusinessRuleError({"detail": "Ngựa này đang có yêu cầu chờ duyệt.",
                                         "code": "PENDING_REQUEST_EXISTS", "RequestID": pending.id})
            if set(changes) - set(COLUMNS):
                raise BusinessRuleError("Có trường không được phép đề nghị sửa.", "FIELD_NOT_EDITABLE")
            validator = HorseWriteSerializer(horse, data=changes, partial=True)
            validator.is_valid(raise_exception=True)
            items = []
            for attr, new in validator.validated_data.items():
                old = scalar(getattr(horse, attr))
                if scalar(new) != old:
                    items.append({"Field": Horse._meta.get_field(attr).db_column,
                                  "OldValue": old, "NewValue": scalar(new)})
            docs = {d.id: d for d in horse.documents.filter(is_visible_to_owner=True, is_retired=False)}

            def visible(doc_id):
                doc = docs.get(doc_id)
                if doc is None:
                    raise ValidationError({"Documents": ["Tài liệu không thuộc hồ sơ hoặc không được phép sử dụng."]})
                return doc

            evidence_ids = list(dict.fromkeys(options.get("EvidenceDocumentIDs", []) +
                                            ([evidence_document_id] if evidence_document_id else [])))
            evidence = [document_info(visible(i)) for i in evidence_ids]
            avatar_id = options.get("AvatarDocumentID")
            if avatar_id and not is_image(visible(avatar_id)):
                raise ValidationError({"AvatarDocumentID": ["Cần chọn ảnh trong hồ sơ."]})
            remove_ids = list(dict.fromkeys(options.get("RemoveImageIDs", [])))
            removed = []
            for doc_id in remove_ids:
                doc = visible(doc_id)
                if not is_image(doc) or doc.uploaded_by_id != user.pk:
                    raise PermissionDenied("Chỉ đề nghị gỡ ảnh do chính bạn tải lên.")
                removed.append(document_info(doc))
            if avatar_id in remove_ids:
                raise ValidationError({"AvatarDocumentID": ["Ảnh đại diện đề nghị đang được chọn gỡ."]})
            if set(remove_ids) & set(evidence_ids):
                raise ValidationError({"Documents": ["Ảnh được gỡ không thể đồng thời làm minh chứng."]})
            metadata = ChangeAttachmentSerializer(data=options.get("Attachments", []), many=True)
            metadata.is_valid(raise_exception=True)
            attachments = metadata.validated_data
            max_files = getattr(settings, "CHANGE_REQUEST_MAX_FILES", 12)
            if len(attachments) > max_files:
                raise ValidationError({"Attachments": [f"Tối đa {max_files} file trong một yêu cầu."]})
            files = files or {}
            keys = [a["FileKey"] for a in attachments]
            if len(set(keys)) != len(keys) or set(files) != set(keys) or any(len(files.getlist(k)) != 1 for k in keys):
                raise ValidationError({"Attachments": ["Danh sách file không khớp với nội dung yêu cầu."]})
            avatars = sum(a["Purpose"] == "avatar" for a in attachments) + bool(avatar_id)
            if avatars > 1:
                raise ValidationError({"AvatarDocumentID": ["Chỉ chọn một ảnh đại diện đề nghị."]})
            images = [d for d in docs.values() if is_image(d)]
            current_avatar = next((d for d in images if d.is_primary), images[0] if images else None)
            if current_avatar and current_avatar.id in remove_ids and not avatars:
                raise ValidationError({"AvatarDocumentID": ["Cần chọn ảnh thay thế trước khi gỡ ảnh đại diện."]})
            if avatar_id and current_avatar and avatar_id == current_avatar.id:
                avatar_id = None  # selecting the current avatar is not a change
            replacements = set()
            for index, item in enumerate(attachments):
                file = files[item["FileKey"]]
                try:
                    ext = store.validate_upload(file)
                except ValidationError as exc:
                    raise ValidationError({item["FileKey"]: exc.detail.get("File", ["File không hợp lệ."])})
                if item["Purpose"] in ("avatar", "image") and ext == ".pdf":
                    raise ValidationError({item["FileKey"]: ["Ảnh chỉ nhận JPG, PNG hoặc WebP."]})
                if item["Purpose"] in ("avatar", "image"):
                    item["DocumentType"] = "Other"
                old_id = item.get("ReplacesDocumentID")
                if item["Purpose"] == "replace":
                    old = visible(old_id)
                    if old.uploaded_by_id != user.pk or old.document_type in ("Contract", "Handover Record") or is_image(old):
                        raise PermissionDenied("Không được thay tài liệu hoặc ảnh do chuyên môn quản lý; hãy bổ sung tài liệu riêng.")
                    if old_id in replacements or old_id in evidence_ids:
                        raise ValidationError({"Documents": ["Tài liệu bị chọn trùng để thay thế hoặc làm minh chứng."]})
                    replacements.add(old_id)
                    item["CurrentDocument"] = document_info(old)
                    # Preserve document classification across versions.
                    item["DocumentType"] = old.document_type
                elif old_id:
                    raise ValidationError({"Documents": ["Chỉ mục đích thay thế mới có tài liệu cũ."]})
                item["OriginalName"] = Path(file.name.replace("\\", "/")).name[:150]
                item["Size"] = file.size
                item["ContentType"] = store.content_type("x" + ext)
            if not items and not any(a["Purpose"] != "evidence" for a in attachments) and not remove_ids and not avatar_id:
                raise BusinessRuleError("Chưa có thay đổi hợp lệ. Giá trị đề nghị đang giống hồ sơ hiện tại.", "NO_CHANGES")
            for item in attachments:
                path = store.save_upload(horse.id, files[item["FileKey"]])
                saved_files.append(path)
                item["StoredFile"] = path
                item.pop("FileKey")
            payload = {"Version": 2, "Reason": reason, "Changes": items,
                       "Snapshot": snapshot(horse), "Attachments": attachments,
                       "EvidenceDocuments": evidence, "RemovedImages": removed,
                       "CurrentAvatar": document_info(current_avatar) if current_avatar else None,
                       "AvatarDocument": document_info(visible(avatar_id)) if avatar_id else None}
            result = ProfileChangeRequest.objects.create(
                horse=horse, requested_by=user, changed_fields=json.dumps(payload, ensure_ascii=False),
                evidence_document_id=evidence_document_id)
            log_action(user, "REQUEST_PROFILE_CHANGE", horse, {"ProfileChangeRequestID": result.id})
            return result
    except Exception:
        for path in saved_files:
            store.delete_file(path)
        raise


def lock_request(request):
    # Always lock horse before request (same order as submission).
    horse = Horse.objects.select_for_update().get(pk=request.horse_id)
    request = ProfileChangeRequest.objects.select_for_update().get(pk=request.pk)
    if request.status != "Pending":
        raise BusinessRuleError("Yêu cầu này đã được xử lý.", "INVALID_STATUS")
    return horse, request


@transaction.atomic
def approve(request, user, note=None):
    horse, request = lock_request(request)
    require_reviewer(horse, user)
    require_approved(horse)
    payload = json.loads(request.changed_fields)
    if payload.get("Snapshot"):
        stale = snapshot(horse) != payload["Snapshot"]
    else:  # Backwards compatible with existing single/multi-field proposals.
        stale = any(scalar(getattr(horse, COLUMNS[i["Field"]])) != i["OldValue"] for i in payload["Changes"])
    if stale:
        raise BusinessRuleError("Hồ sơ đã thay đổi từ lúc gửi. Hãy từ chối để Owner tạo yêu cầu mới.", "STALE_PROFILE")
    data = {i["Field"]: i["NewValue"] for i in payload["Changes"]}
    validator = HorseWriteSerializer(horse, data=data, partial=True)
    validator.is_valid(raise_exception=True)
    for item in payload.get("Attachments", []):
        if not store.stored_path(item["StoredFile"]).is_file():
            raise BusinessRuleError("Không tìm thấy file đề nghị trên máy chủ.", "FILE_MISSING")
    validator.save()
    # Freeze the implicit legacy avatar before adding new images.
    current_avatar = payload.get("CurrentAvatar")
    if current_avatar:
        horse.documents.filter(pk=current_avatar["DocumentID"]).update(is_primary=True)
    avatar_id = (payload.get("AvatarDocument") or {}).get("DocumentID")
    for item in payload.get("Attachments", []):
        if item["Purpose"] == "evidence":
            continue
        old_id = item.get("ReplacesDocumentID")
        doc = HorseDocument.objects.create(
            horse=horse, document_name=item["DocumentName"], document_type=item["DocumentType"],
            file_url=item["StoredFile"], uploaded_by_id=request.requested_by_id,
            is_profile_image=item["Purpose"] in ("avatar", "image"),
            replaces_document_id=old_id)
        item["AppliedDocumentID"] = doc.id
        if old_id:
            horse.documents.filter(pk=old_id).update(is_retired=True, is_primary=False)
        if item["Purpose"] == "avatar":
            avatar_id = doc.id
    for item in payload.get("RemovedImages", []):
        horse.documents.filter(pk=item["DocumentID"]).update(is_retired=True, is_primary=False)
    if avatar_id:
        horse.documents.update(is_primary=False)
        horse.documents.filter(pk=avatar_id, is_retired=False).update(is_primary=True)
    horse.touch()
    horse.save(update_fields=["updated_at"])
    request.changed_fields = json.dumps(payload, ensure_ascii=False)
    return finish(request, user, "Approved", note)


@transaction.atomic
def reject(request, user, note):
    horse, request = lock_request(request)
    require_reviewer(horse, user)
    if not note or not note.strip():
        raise BusinessRuleError("Cần ghi lý do từ chối.", "REVIEW_NOTE_REQUIRED")
    return finish(request, user, "Rejected", note)


@transaction.atomic
def withdraw(request, user):
    horse, request = lock_request(request)
    require_owner(horse, user)
    if request.requested_by_id != user.pk:
        raise PermissionDenied("Chỉ người gửi được rút yêu cầu.")
    return finish(request, user, "Withdrawn", "Owner đã rút yêu cầu.")


def finish(request, user, status, note):
    request.status, request.reviewed_by, request.reviewed_at = status, user, timezone.now()
    request.review_note = note or None
    request.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "changed_fields"])
    log_action(user, {"Approved": "APPROVE_PROFILE_CHANGE", "Rejected": "REJECT_PROFILE_CHANGE",
                      "Withdrawn": "WITHDRAW_PROFILE_CHANGE"}[status],
               request.horse, {"ProfileChangeRequestID": request.id})
    return request
