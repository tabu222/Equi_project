"""
Email Flow 2 gửi chủ ngựa (dùng apps.core.emails.send_email: gửi sau khi lưu database, lỗi không làm hỏng thao tác).

Chỉ gửi việc quan trọng; kết quả từng buổi tập chỉ hiện trên trang Huấn luyện + chuông thông báo:
  - giáo án mới được duyệt
  - trainer chốt giai đoạn -> tổng kết giai đoạn
  - giáo án kết thúc -> tổng kết cả giáo án
  - buổi tập bị dừng giữa chừng vì ngựa có vấn đề (khẩn)
"""
from apps.core.emails import send_email


def _owner(horse):
    return [horse.owner.email] if horse.owner_id and horse.owner.email else []


def _label(horse):
    return f"{horse.horse_name}" + (f" ({horse.horse_code})" if horse.horse_code else "")


def _number(value, unit=""):
    if value is None:
        return "—"
    text = f"{value:,.1f}".replace(",", " ").replace(".", ",").removesuffix(",0")
    return f"{text}{unit}"


def _summary_lines(summary):
    lines = [
        f"Thời gian: {summary['From']:%d/%m/%Y} → {summary['To']:%d/%m/%Y}",
        f"Buổi tập: {summary['CompletedSessions']}/{summary['PlannedSessions']} hoàn thành"
        f" · {summary['CancelledSessions']} hủy · {summary['MissedSessions']} vắng",
    ]
    distance = f"Quãng đường: {_number(summary['TotalDistanceKm'], ' km')}"
    if summary["DistanceTargetKm"]:
        distance += (f" / mục tiêu {_number(summary['DistanceTargetKm'], ' km')}"
                     f" ({_number(summary['DistanceProgressPercent'], '%')})")
    lines.append(distance)
    lines.append(f"Tốc độ TB: {_number(summary['AvgSpeedKmh'], ' km/h')}"
                 f" · Điểm phong độ TB: {_number(summary['AvgPerformanceScore'], '/100')}")
    evaluations = " · ".join(f"{count} {name}" for name, count in summary["Evaluations"].items() if count)
    lines.append(f"Đánh giá của trainer: {evaluations or 'chưa có'}")
    if summary.get("Health"):
        lines.append(f"Sức khỏe: {summary['Health']['Text']}")
    return lines


def plan_approved(plan):
    horse = plan.assignment.horse
    end = f" → {plan.end_date:%d/%m/%Y}" if plan.end_date else ""
    stages = "\n".join(f"  {s.stage_order}. {s.stage_name} "
                       + (f"({s.start_date:%d/%m} → {s.end_date:%d/%m})" if s.end_date else f"(từ {s.start_date:%d/%m})")
                       for s in plan.stages.all())
    send_email(_owner(horse), f"Giáo án mới cho {horse.horse_name}", (
        f"Chào {horse.owner.full_name},\n\n"
        f"Giáo án huấn luyện mới của {_label(horse)} đã được duyệt.\n"
        f"Mục tiêu: {plan.goal or '—'}\n"
        f"Trainer phụ trách: {plan.assignment.trainer.full_name}\n"
        f"Thời gian: {plan.start_date:%d/%m/%Y}{end}\n"
        f"Các giai đoạn:\n{stages}\n\n"
        "Bạn sẽ nhận tổng kết khi kết thúc mỗi giai đoạn; kết quả từng buổi tập xem trong mục Huấn luyện."
    ))


def stage_closed(stage):
    from .summaries import plan_summary

    plan = stage.plan
    horse = plan.assignment.horse
    row = next(s for s in plan_summary(plan)["Stages"] if s["TrainingPlanStageID"] == stage.id)
    lines = _summary_lines(row["Summary"])
    diff = row["ComparedToPreviousStage"]
    if diff and diff.get("AvgPerformanceScore") is not None:
        lines.append(f"So với giai đoạn trước: điểm TB {diff['AvgPerformanceScore']:+.1f}".replace(".", ","))
    send_email(_owner(horse), f"Tổng kết giai đoạn {stage.stage_order} – {stage.stage_name} · {horse.horse_name}", (
        f"Chào {horse.owner.full_name},\n\n"
        f"Trainer {plan.assignment.trainer.full_name} đã chốt giai đoạn \"{stage.stage_name}\" "
        f"trong giáo án \"{plan.goal or f'#{plan.id}'}\" của {_label(horse)}.\n\n"
        + "\n".join(lines)
        + (f"\n\nNhận xét của trainer: {stage.summary_note}" if stage.summary_note else "")
        + "\n\nXem chi tiết từng buổi tập trong mục Huấn luyện."
    ))


def plan_completed(plan):
    from .summaries import plan_summary

    horse = plan.assignment.horse
    body = plan_summary(plan)
    stages = "\n".join(
        f"  {s['StageOrder']}. {s['StageName']}: "
        + (f"{s['Summary']['CompletedSessions']} buổi, {_number(s['Summary']['TotalDistanceKm'], ' km')}, "
           f"điểm TB {_number(s['Summary']['AvgPerformanceScore'])}" if s["Summary"] else "không thực hiện")
        for s in body["Stages"])
    send_email(_owner(horse), f"Tổng kết giáo án · {horse.horse_name}", (
        f"Chào {horse.owner.full_name},\n\n"
        f"Giáo án \"{plan.goal or f'#{plan.id}'}\" của {_label(horse)} đã kết thúc.\n\n"
        + "\n".join(_summary_lines(body["Summary"]))
        + f"\n\nTừng giai đoạn:\n{stages}\n\nXem chi tiết trong mục Huấn luyện."
    ))


def session_stopped(session, reason):
    horse = session.horse
    send_email(_owner(horse), f"[Khẩn] Buổi tập của {horse.horse_name} bị dừng", (
        f"Chào {horse.owner.full_name},\n\n"
        f"Buổi tập {session.training_type} ngày {session.session_date:%d/%m/%Y} của {_label(horse)} "
        f"đã bị dừng.\nLý do: {reason}\n\n"
        "Trainer và bác sĩ thú y của câu lạc bộ đang theo dõi; bạn sẽ được báo khi có thêm thông tin."
    ))
