import { ApiError, apiBaseUrl, apiGet, apiPost } from './apiClient.ts';
import { normalizeHorse, getMedicalRecords, type MedicalRecord } from './horseApi.ts';
import type { Horse } from '../types';

type Row = Record<string, unknown>;

// Follow every page before presenting herd totals. Never follow an arbitrary next URL with JWT.
export async function getCompleteVetList(path: string): Promise<Row[]> {
  const base = new URL(`${apiBaseUrl}/`, window.location.origin);
  const resource = new URL(`${base.href}${path.replace(/^\//, '')}`);
  const visited = new Set<string>();
  const rows: Row[] = [];
  let next: string | null = path;
  let expected: number | undefined;
  while (next) {
    if (visited.has(next) || visited.size >= 1000) throw new ApiError('Không thể tải đầy đủ danh sách. Vui lòng thử lại.');
    visited.add(next);
    const response: unknown = await apiGet(next);
    if (Array.isArray(response)) {
      if (visited.size !== 1) throw new ApiError('Danh sách thay đổi trong lúc tải. Vui lòng thử lại.');
      return response;
    }
    const page = response as { results?: Row[]; count?: number; next?: string | null } | null;
    if (!page || !Array.isArray(page.results) || !Number.isInteger(page.count) || (page.count ?? -1) < 0
      || (page.next !== null && typeof page.next !== 'string')) throw new ApiError('Không thể xác nhận danh sách đầy đủ.');
    if (expected !== undefined && expected !== page.count) throw new ApiError('Danh sách thay đổi trong lúc tải. Vui lòng thử lại.');
    expected = page.count;
    rows.push(...page.results);
    next = null;
    if (page.next) {
      const url = new URL(page.next, resource);
      if (url.origin !== base.origin || url.pathname !== resource.pathname || url.hash || url.username || url.password)
        throw new ApiError('Không thể tải trang tiếp theo của danh sách.');
      next = `${path.split('?')[0]}${url.search}`;
    }
  }
  if (rows.length !== expected) throw new ApiError('Danh sách chưa đầy đủ. Vui lòng thử lại.');
  return rows;
}

export async function getVetHerd(clubId: string): Promise<Horse[]> {
  const horses = (await getCompleteVetList('/horses')).map(normalizeHorse);
  if (!clubId || horses.some((horse) => horse.clubId !== clubId) || new Set(horses.map(h => h.id)).size !== horses.length)
    throw new ApiError('Không thể xác nhận phạm vi đàn ngựa. Vui lòng tải lại.');
  return horses;
}

export interface VetStall { id: string; number: string; type: string; status: string; horseId?: string }
export async function getVetStalls(clubId: string): Promise<VetStall[]> {
  return (await getCompleteVetList('/stalls')).map((row) => {
    if (String(row.ClubID) !== clubId || row.StallID == null || typeof row.StallNumber !== 'string')
      throw new ApiError('Không thể xác nhận dữ liệu chuồng.');
    const horse = row.CurrentHorse as Row | null;
    return { id: String(row.StallID), number: row.StallNumber, type: String(row.StallType ?? ''),
      status: String(row.Status ?? ''), horseId: horse?.HorseID == null ? undefined : String(horse.HorseID) };
  });
}

export interface VetHistory { records: MedicalRecord[]; failedHorseIds: string[] }
// Temporary adapter for the existing per-horse contract; bounded concurrency, no silent failures.
export async function getVetHistories(horses: Horse[]): Promise<VetHistory> {
  const records: MedicalRecord[] = [];
  const failedHorseIds: string[] = [];
  let cursor = 0;
  await Promise.all(Array.from({ length: Math.min(4, horses.length) }, async () => {
    while (cursor < horses.length) {
      const horse = horses[cursor++];
      try { records.push(...await getMedicalRecords(horse.id)); }
      catch { failedHorseIds.push(horse.id); }
    }
  }));
  return { records, failedHorseIds };
}

export interface MedicalAmendment { id: string; reason: string; content: string; author: string; at: string }
function amendment(row: Row): MedicalAmendment {
  return { id: String(row.MedicalRecordAmendmentID), reason: String(row.Reason ?? ''),
    content: String(row.AmendedContent ?? ''), author: String(row.AmendedByName ?? ''), at: String(row.AmendedAt ?? '') };
}
export async function getMedicalAmendments(id: string): Promise<MedicalAmendment[]> {
  return (await getCompleteVetList(`/medical-records/${encodeURIComponent(id)}/amendments`)).map(amendment);
}
export async function addMedicalAmendment(id: string, reason: string, content: string): Promise<MedicalAmendment> {
  return amendment(await apiPost<Row>(`/medical-records/${encodeURIComponent(id)}/amendments`, {
    Reason: reason.trim(), AmendedContent: content.trim(),
  }));
}
