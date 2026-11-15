-- One row per finished image job: features known BEFORE processing + quality metrics AFTER.
-- Export to CSV (from the repo root, with `docker compose up` running):
--   docker compose exec -T postgres psql -U animeshka -d animeshka --csv -f - < analytics/export_features.sql > analytics/dataset/runs.csv
SELECT
    j.id                                                            AS job_id,
    j.created_at,
    j.original_filename                                             AS filename,
    j.mode,
    fi.width                                                        AS width,
    fi.height                                                       AS height,
    fi.size_bytes                                                   AS input_bytes,
    max(m.value) FILTER (WHERE m.name = 'input_megapixels')         AS input_megapixels,
    max(m.value) FILTER (WHERE m.name = 'sharpness_input')          AS sharpness_input,
    max(m.value) FILTER (WHERE m.name = 'processing_seconds')       AS processing_seconds,
    max(m.value) FILTER (WHERE m.name = 'output_megapixels')        AS output_megapixels,
    max(m.value) FILTER (WHERE m.name = 'psnr_db')                  AS psnr_db,
    max(m.value) FILTER (WHERE m.name = 'ssim')                     AS ssim,
    max(m.value) FILTER (WHERE m.name = 'sharpness_bicubic')        AS sharpness_bicubic,
    max(m.value) FILTER (WHERE m.name = 'sharpness_output')         AS sharpness_output
FROM jobs j
JOIN files fi ON fi.job_id = j.id AND fi.role = 'input'
LEFT JOIN metrics m ON m.job_id = j.id
WHERE j.kind = 'image' AND j.status = 'done'
GROUP BY j.id, j.created_at, j.original_filename, j.mode, fi.width, fi.height, fi.size_bytes
HAVING max(m.value) FILTER (WHERE m.name = 'psnr_db') IS NOT NULL
ORDER BY j.created_at;
