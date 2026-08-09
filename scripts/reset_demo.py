from pathlib import Path
p=Path("data/zhilin.db")
if p.exists(): p.unlink()
print("演示数据库已删除；请执行 python -m data.seed 重新生成。")

