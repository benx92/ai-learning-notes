"""可选展示实验；先安装Rich，不连接业务或模型。"""
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from rich.text import Text


def main():
    console = Console()
    table = Table(title="教学任务状态")
    table.add_column("任务")
    table.add_column("阶段")
    table.add_row(Text("return-32"), Text("等待确认"))
    console.print(table)
    console.print("外部内容：[red]仍按原样显示[/red]", markup=False, highlight=False)
    with Progress(console=console) as progress:
        task = progress.add_task("核对已知的三项教学结果", total=3)
        for _ in range(3):
            progress.advance(task)


if __name__ == "__main__":
    main()
