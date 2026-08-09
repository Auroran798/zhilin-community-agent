# Stage 5 requirement conflicts

1. The requested release checklist requires a clean dependency/image/config scanner result, while this host's shared Python environment contains many packages outside this repository and Trivy is absent. Treating that as project-clean would be misleading, so the release gate reports it as unresolved.
2. The requested video is optional when the runtime lacks browser/video support. Local Chrome enabled real browser E2E and screenshots, but Playwright ffmpeg is missing; an executable recording script is supplied and the completion material must not claim a generated video.
3. The repository is an uncommitted initial worktree (no `HEAD`), so the generated manifest records `uncommitted-worktree` rather than fabricating a commit identifier.
