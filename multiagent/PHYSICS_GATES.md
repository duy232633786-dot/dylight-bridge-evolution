# Physics-in-the-loop + Reality-in-the-loop — PG-1.0

## Thứ bậc bằng chứng

Đo hiện trường/thử nghiệm đã hiệu chuẩn > L3/L2 đã verification & validation >
L1 > surrogate > LLM. AI, NotebookLM và hình render chỉ sinh giả thuyết. Solver
failed, không hội tụ, sai đơn vị, thiếu tải/site/material data đều là `STOP`.

## Fidelity ladder

- **F0 IDEA:** topology/hình dạng và giả thuyết load path; không có claim kỹ thuật.
- **F1 SCREENED:** L0/L1, cân bằng sơ bộ, hard geometry/manufacturing constraints.
- **F2 3D LINEAR VERIFIED:** grillage/shell/solid phù hợp, moving loads, stability,
  mesh convergence, sensitivity BC/load và đối chiếu solver/phương pháp độc lập.
- **F3 NONLINEAR/STAGED VERIFIED:** phi tuyến hình học/vật liệu, DƯL và mất mát,
  trình tự thi công, co ngót–từ biến, contact/gối/liên kết, khuyết tật và uncertainty.
- **F4 HAZARD/MULTIPHYSICS:** applicability cho gió/đàn hồi khí, động đất–nền,
  thủy lực/xói, mỏi/phá hủy, nhiệt/cháy, ăn mòn, va chạm và progressive collapse.
- **F5 LAB VALIDATED:** coupon → component → subassembly/scale model; test plan
  pre-registered, sensor calibration, raw immutable data, repeatability/uncertainty,
  blind prediction và model–test correlation.
- **F6 PILOT/FIELD VALIDATED:** mock-up/công trình thí điểm, proof/static/dynamic
  test theo authority, SHM baseline, load/environment metadata và model updating.
- **F7 ENGINEERING CANDIDATE:** independent design check, construction/inspection/
  repair plan, LCCA/carbon, residual risks và human/code-owner sign-off.

## Gate bắt buộc

- **G0 — Design basis:** khóa SI units, hệ tọa độ, site/span/system, clearance,
  design life, codes/version, geotech/hydraulic/wind/seismic exposure, loads và
  combinations. Thiếu dữ liệu thì dừng.
- **G1 — Geometry & reality:** topology hợp lệ; clash-free; parametric repeatable;
  fabrication, tolerances, transport, lift, erection và inspection access đạt.
- **G2 — Model quality:** equilibrium/reactions, dimension checks, material domain,
  BC/load traceability, element suitability, mesh/time-step convergence, benchmark,
  solver version/hash; không còn numerical warning chưa xử lý.
- **G3 — Limit states:** strength, serviceability, stability, fatigue, robustness,
  dynamics, durability và construction stages có margin theo design basis.
- **G4 — Independent verification:** blind re-calculation bằng analyst khác và
  solver/phương pháp khác; chênh lệch vượt tolerance phải reconcile, không lấy trung bình.
- **G5 — Physical test:** plan duyệt trước, calibration ID, raw data, uncertainty,
  repeatability, failure mode/load path và model discrepancy trong tolerance.
- **G6 — Material & exposure:** batch/composition/process provenance; characteristic
  properties; creep/shrinkage/fatigue/fracture/fire/chemical durability; interfaces,
  repair/recycling; supplier quote; EPD boundary; design-life degradation model.
- **G7 — Release:** QA/QC, constructability, inspection/maintenance/replaceability,
  residual hazard, lifecycle cost/carbon, independent report và human sign-off.

Hazard có thể `NOT_APPLICABLE` chỉ khi design basis nêu lý do và reviewer duyệt.
Hard safety gate không được đổi lấy chi phí, carbon, độ mới hay thẩm mỹ.
