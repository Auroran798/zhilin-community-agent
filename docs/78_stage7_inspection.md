# Stage 7 巡检与整改

inspection_plans 支持 daily、weekly、monthly；同一计划与周期通过 uq_inspection_task_plan_period 保证至多一个任务。维修/巡检人员提交记录后，异常可由客服/经理创建整改单。

整改流转为待整改/整改中 → 待复查 → 已关闭或整改中。critical/high 风险没有自动关闭路径，必须由经理人工复查。
