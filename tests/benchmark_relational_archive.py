"""Synthetic micro-benchmark; reports Python-traced peak allocation, not RSS."""
from __future__ import annotations

import gc
import json
from pathlib import Path
import sys
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from relational_fixture import make_payload
import relational_archive as archive
import relational_model as model


def measure(fn):
    gc.collect()
    current_before, _ = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    started = time.perf_counter()
    result = fn()
    elapsed_ms = (time.perf_counter() - started) * 1000
    _, peak = tracemalloc.get_traced_memory()
    return result, round(elapsed_ms, 2), max(0, peak - current_before)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def run():
    tracemalloc.start()
    results = []
    for size in (20, 100, 500):
        payload = make_payload(size, long_text_repeat=2)
        source_bytes = len(canonical(payload).encode("utf-8"))
        dataset, stage_ms, stage_mem = measure(lambda: model.capture_r8_source(payload))
        _, validate_ms, validate_mem = measure(lambda: archive.validate_archive_dataset(dataset))
        zip_bytes, zip_export_ms, zip_export_mem = measure(lambda: archive.export_zip(dataset))
        zip_dataset, zip_import_ms, zip_import_mem = measure(lambda: archive.import_zip(zip_bytes))
        zip_payload, zip_rebuild_ms, zip_rebuild_mem = measure(lambda: model.reconstruct_r8_payload(zip_dataset))
        xlsx_bytes, xlsx_export_ms, xlsx_export_mem = measure(lambda: archive.export_xlsx(dataset))
        xlsx_dataset, xlsx_import_ms, xlsx_import_mem = measure(lambda: archive.import_xlsx(xlsx_bytes))
        xlsx_payload, xlsx_rebuild_ms, xlsx_rebuild_mem = measure(lambda: model.reconstruct_r8_payload(xlsx_dataset))
        if canonical(zip_payload) != canonical(payload) or canonical(xlsx_payload) != canonical(payload):
            raise AssertionError(f"Round-trip semantic mismatch at {size} patients")
        results.append({
            "patients": size,
            "logical_rows": sum(len(dataset[name]) for name in model.TABLES),
            "source_payload_bytes": source_bytes,
            "stage_ms": stage_ms,
            "validation_ms": validate_ms,
            "zip_bytes": len(zip_bytes), "zip_export_ms": zip_export_ms, "zip_import_ms": zip_import_ms,
            "zip_reconstruct_ms": zip_rebuild_ms,
            "xlsx_bytes": len(xlsx_bytes), "xlsx_export_ms": xlsx_export_ms, "xlsx_import_ms": xlsx_import_ms,
            "xlsx_reconstruct_ms": xlsx_rebuild_ms,
            "python_peak_extra_bytes": {"stage": stage_mem, "validation": validate_mem,
                "zip_export": zip_export_mem, "zip_import": zip_import_mem, "zip_reconstruct": zip_rebuild_mem,
                "xlsx_export": xlsx_export_mem, "xlsx_import": xlsx_import_mem, "xlsx_reconstruct": xlsx_rebuild_mem},
        })
        del payload, dataset, zip_bytes, zip_dataset, zip_payload, xlsx_bytes, xlsx_dataset, xlsx_payload
    tracemalloc.stop()
    print(json.dumps({"measurement": "single local run; tracemalloc Python allocations (not process RSS)", "results": results}, indent=2))


if __name__ == "__main__": run()
