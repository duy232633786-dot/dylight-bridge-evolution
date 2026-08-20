# 02 — Agent Protocol P6 (legacy)

> **Đã được thay thế ở v0.7.0:** protocol này được giữ làm lịch sử. Mọi agent
> mới phải dùng `docs/05_multi_agent_research_protocol.md` và `multiagent/`.
> Claude không còn là coordinator độc quyền; vai trò được gán theo task và
> người thực hiện không được tự review.

Phiên bản: AP-0.1 (draft). Định hướng công cụ đã chốt: **não 1 = Claude (Desktop/Code)**,
**mô hình BIM = Revit** (revit-mcp), **phân tích kiểm chứng = Midas Civil** (MCP, giai đoạn L2).

## Phân vai bất biến

| Thành phần | Được làm | Cấm |
|---|---|---|
| Claude (não 1 — planner) | Lập kế hoạch, gọi tool, đọc kết quả, đề xuất sửa, viết báo cáo | Tự tính nội lực, tự kết luận PASS/FAIL, bịa số liệu |
| Knowledge layer (não 2) | Gợi ý hướng sửa, giải thích, cung cấp án lệ | Kết luận đạt/không đạt; cung cấp con số không đối chiếu catalog |
| Obsidian | Hiển thị dashboard/card, liên kết và ghi chú cho não 2 | Trở thành verifier; tự ghi ngược Markdown vào runtime JSON |
| Solver + Verifier (lõi vật lý) | Nguồn DUY NHẤT của mọi con số phản ứng và PASS/FAIL | — |
| Con người (kỹ sư) | Duyệt gold cases, duyệt knowledge cards, phê duyệt phương án cuối | — |

## Vòng lặp chuẩn của planner

```
1. Đọc yêu cầu → xác nhận project_inputs (nếu thiếu: hỏi người dùng, KHÔNG tự bịa)
2. Sinh/chọn phương án ứng viên   →  python -m bridge_evolution.cli evaluate <state.json>
3. Nếu FAIL:
   a. Đọc violations trong EvaluationResult
   b. Hỏi tầng chẩn đoán          →  suggest_repairs(state, result)   [kèm card_id não 2]
   c. Chọn 1 nước sửa, quay lại bước 2 (ghi parent_candidate_id để giữ phả hệ)
4. Nếu cần tối ưu:                →  experiments/run_baseline.py | run_multiseed.py
5. Đề cử top ứng viên từ Pareto archive → trình con người phê duyệt
6. Sau phê duyệt: dựng BIM Revit (revit-mcp) + hồ sơ kiểm chứng L2 (Midas Civil)
```

## Quy tắc an toàn cho planner

1. Mọi con số trong báo cáo phải trích được từ một `EvaluationResult` có `input_hash` —
   không có hash thì không có con số.
2. Không bao giờ đề xuất phương án có bất kỳ HARD violation nào, kể cả khi "chỉ vi phạm nhẹ".
3. `SOLVER_FAILED` = lỗi dữ liệu/mô hình → dừng và báo người, không né bằng cách đổi thiết kế.
4. Kết quả tối ưu chỉ được diễn giải trong phạm vi fidelity đã chạy (L1 = sơ bộ;
   kết luận cuối cần L2 Midas + kỹ sư duyệt).
5. Mọi thẻ tri thức DRAFT chỉ được dùng làm gợi ý kèm ghi chú "chưa được kỹ sư duyệt".
6. Planner phải đọc `risk`, `claim_audit` và evidence hash trên note Obsidian;
   card RED/legacy không được dùng làm bằng chứng định lượng.

## Obsidian và não 2

`knowledge-export` sinh một snapshot Markdown có manifest từ KnowledgeCard JSON.
Exporter không sửa `.obsidian/`, không xóa note lạ và không ghi đè note đã được
người dùng chỉnh. Obsidian là bề mặt đọc/ghi chú; `load_cards()` vẫn chỉ nạp JSON
đã validate. Xem contract đầy đủ tại `docs/04_obsidian_integration.md`.

## Lộ trình nối MCP (chưa triển khai — thứ tự dự kiến)

1. Bọc `evaluate_candidate` + `suggest_repairs` + `query_knowledge` thành MCP tools
   (hoặc dùng trực tiếp qua CLI trong Claude Code — đang dùng được ngay).
2. Adapter Midas Civil NX Open API (JSON): dựng model từ `BridgeDesignState`,
   chạy phân tích, đọc nội lực về `analysis_result` — điền vào `fe_adapter/solver.py::MIDAS_CIVIL`.
3. Adapter Revit (revit-mcp đã có): dựng LOD 300 từ state đã APPROVED, ghi `bim_guid_map`
   vào provenance để khép kín ánh xạ biến ↔ BIM ↔ FE ↔ rule.
