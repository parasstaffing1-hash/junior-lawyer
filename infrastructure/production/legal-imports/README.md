# Controlled legal-data import drop

Place normalized `.json` legal-data manifests here only when using a Batch-26 `filesystem_drop` feed. The production API/worker mounts this directory read-only at `/data/legal-imports`. Feed `import_path` values are relative to that root. Do not place credentials or raw privileged client files here.
