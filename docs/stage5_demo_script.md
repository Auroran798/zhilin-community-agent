# Stage 5 demo script

1. Run `docker compose up --build -d`, then open `http://localhost:8501` and `http://localhost:8000/ready`.
2. Sign in as `resident_demo`; send a normal repair request, review the preview and confirm it.
3. Send “电梯困人”; show the emergency/manual-handoff result rather than an automated resolution.
4. Ask a policy question and show the cited knowledge answer; ask an unsupported question and show the refusal.
5. Sign in as customer service, accept and assign the repair. Sign in as maintenance, complete only the assigned task.
6. Return as resident to view progress, confirm completion and submit a rating.
7. Create an announcement draft as customer service; approve and publish it only as manager.
8. Submit an inspection abnormality, create rectification, complete it as assigned maintenance and review it as manager.
9. Open dashboard, audit logs and observability trace pages. Demonstrate that a resident cannot view another resident's bill.

This is an 8–15 minute single-host Demo. It does not demonstrate real payment, access control, cameras or a production deployment.
