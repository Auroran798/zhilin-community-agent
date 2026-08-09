# Stage 7 测试报告

执行命令：

    python -m alembic upgrade head
    python -m alembic check
    python -m pytest -q

结果：41 passed，0 failed，0 skipped。

| 测试集 | total | passed | failed | skipped |
| --- | ---: | ---: | ---: | ---: |
| Stage 1（含集成、种子） | 6 | 6 | 0 | 0 |
| Stage 2 | 3 | 3 | 0 | 0 |
| Stage 3 | 9 | 9 | 0 | 0 |
| Stage 4 | 7 | 7 | 0 | 0 |
| Stage 5 | 3 | 3 | 0 | 0 |
| Stage 6 | 9 | 9 | 0 | 0 |
| Stage 7 | 4 | 4 | 0 | 0 |
| All | 41 | 41 | 0 | 0 |

Stage 7 覆盖报修 SLA/派单/评价、公告审批与定向通知、账单比较和跨用户阻断、巡检计划幂等、critical 整改人工复查、设备历史和 Harness 权限阻断。

仍有来自历史测试夹具的 datetime.utcnow 警告；生产代码已无该调用。第三方 Chroma/Starlette 的兼容性警告不影响测试结果。
