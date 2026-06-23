# Component PDF Samples

This suite tracks electronic component PDF regression samples by brand and
component category. It is for local conversion hardening and recurring layout
regression, not for replacing the P0 Golden Sample release gate.

## Directory Shape

```text
tests/fixtures/component_pdf_samples/
  manifest.yaml
  acceptance-record-template.md
  samples/
    <brand>/
      <category>/
        <sample-id>/
          mineru/
            *_content_list_v2.json
            images/
```

Use lowercase kebab-case for `brand`, `category`, and `sample-id`. Commit only
small, minimized MinerU packages or public samples. Proprietary PDFs and large
outputs should stay outside the repository and be referenced in the manifest.

## Local Loop

1. Reproduce the issue locally with `md2word_main` or a worktree sandbox.
2. Add a minimized MinerU package:

   ```bash
   /Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/manage_component_pdf_samples.py \
     add-mineru-sample \
     --sample-id ti-opamp-opa228-p1-smoke \
     --brand texas-instruments \
     --category op-amp \
     --product OPA228 \
     --title "OPA228 page 1 layout smoke" \
     --source-pdf "md2word_main:test_pdf/OPA228_P1.pdf" \
     --mineru-package /path/to/mineru_result/OPA228_P1.pdf-uuid \
     --tag datasheet \
     --tag op_amp \
     --acceptance-focus "Heading and first paragraph remain readable" \
     --apply
   ```

3. Fix behavior only in `app/conversion`.
4. Run the component regression:

   ```bash
   /Users/sc/miniconda3/envs/md2word/bin/python scripts/dev/run_component_pdf_regression.py
   ```

5. Record manual review with `acceptance-record-template.md` and keep generated
   DOCX/report artifacts under `tests/tmp/` or external evidence storage.

