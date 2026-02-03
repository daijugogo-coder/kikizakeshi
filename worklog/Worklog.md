Worklog – Kikizakeshi (Cloud Run Integrated Version)

Updated: 2026-01-15

1. Background

The previous Kikizakeshi application was deployed inside a standalone GCP project.

Due to the GCP 3-project limit, consolidation into the existing sake-master project was required.

The application has now been rebuilt, containerized, and deployed properly using:
Docker → Artifact Registry → Cloud Run.

The old Kikizakeshi project remains untouched; the new version under sake-master is considered the primary version going forward.

2. Work Summary
2.1 Local Docker verification

Built and executed the application via Docker Desktop.

All components (UI, OCR, LLM integration, static asset delivery) functioned correctly.

No runtime errors.

2.2 Artifact Registry upload

Used the existing Artifact Registry repository in the sake-master project.

Pushed container images with tags such as:

asia-northeast1-docker.pkg.dev/sake-master-481904/kikizakeshi/kikizakeshi:<tag>

2.3 Cloud Run deployment

Deployment target: sake-master project

Service name: kikizakeshi

Region: asia-northeast1

Resulting public URL:

https://kikizakeshi-1020268592604.asia-northeast1.run.app/


This URL remains stable unless the service name, region, or project is changed.

Redeployments with updated images do not modify the URL.

2.4 Vision API permissions

Cloud Run execution service account:

1020268592604-compute@developer.gserviceaccount.com


This SA already has the necessary Vision AI permissions at the project level.

No additional IAM configuration required.

OCR (including barcode extraction) works correctly on Cloud Run.

2.5 Static assets (favicon, icons, CSS)

Verified existence of all icons inside:

/static


HTML references are correct (/static/favicon.ico, /static/favicon.svg, apple-touch-icon.png).

Cloud Run serves the assets correctly; initial issues were caused by browser-side caching.

3. Validation Results

Cloud Run service works end-to-end:

OCR via Vision API

LLM answer generation

Static asset delivery

Multi-language output

Cloud Run revision routing: latest revision receives 100% traffic.

Application works as expected under the consolidated project.

4. Next Tasks
Confirmed TODO

Maintain README.md in its updated English version.

Use the sake-master project as the unified environment moving forward.

Clean up/retire the old Kikizakeshi project later.

Optional Enhancements

UI refinement

Docker image optimization

Domain mapping if long-term public use is required

Additional LLM enhancements (store_custom, season logic, etc.)

5. Notes

Static asset issues are almost always due to browser caching.

Service account verification is easiest via the Cloud Run YAML tab (Classic UI).

The Cloud Run service URL stays constant unless core service properties change.

Deployment path is now standardized:
GitHub → Docker build → Artifact Registry → Cloud Run.