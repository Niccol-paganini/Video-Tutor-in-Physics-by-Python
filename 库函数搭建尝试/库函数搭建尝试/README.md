# Video Tutor 基础物理碰撞与运动演示系统

本项目把物理题文本或文件转换为统一的场景 JSON，再根据物体类型、运动函数和特殊条件生成二维动画。核心功能仅依赖 Python 标准库，未启动本地大模型时也可以使用规则解析。

## 已实现

- 前端输入：直接输入题目；通过文件选择窗口读取 TXT、MD、CSV、JSON、DOCX，安装 `pypdf` 后支持 PDF。
- 本地 AI：通过 HTTP 接入 Ollama，要求模型输出统一 JSON；界面中可编辑并重新应用 JSON。
- AI 输出区：展示运动物体类型、坐标系、每个物体的运动函数、特殊条件、计算指标和讲解要点。
- 基础图形：质点、圆形、长方形、正方形。
- 基础运动：静止、直线运动、抛体运动、圆周运动和安全的自定义 `x(t)`、`y(t)`。
- 特殊模型：一维碰撞、半圆轨道离轨抛出、滑块—木板恰好不冲出。
- 动画输出：坐标网格、完整轨迹、物体实时位置/速度、速度方向、播放/暂停/拖动/倍速。
- 文件输出：导出结构化 JSON；导出当前动画帧为 PostScript。

## 运行

在本目录打开终端：

```powershell
python main.py
```

也可以双击 `run.bat`。

程序启动后会自动加载圆周运动示例。若只想演示，不需要安装 Ollama。

### 本地大模型

1. 安装并启动 Ollama。
2. 准备一个本地模型，例如：`ollama pull qwen2.5:7b`。
3. 在界面顶部填写服务地址和模型名称，点击“检查模型”。
4. 输入题目后点击“调用本地AI”。

模型不可用时，点击“规则解析（离线）”仍可以生成演示场景。

### PDF 文件

PDF输入是唯一的可选依赖：

```powershell
python -m pip install pypdf
```

## 目录结构

```text
main.py              三栏桌面界面、文件选择和动画控制
models.py            统一数据模型
data_interface.py    文件读取、JSON校验和离线题目解析
ai_service.py        Ollama HTTP接口与结构化提示词
ai接口.py             对原中文模块名的兼容入口
physics_engine.py    运动函数、碰撞和特殊模型计算
render_engine.py     Tkinter物理动画画布
examples/            可直接从界面载入的场景JSON
tests/               核心公式、解析器和安全性测试
```

## 处理流程

```text
题目文字/文件
    ↓
规则解析 或 Ollama结构化分析
    ↓
ProblemSpec统一JSON
    ├─ 物体类型与图形
    ├─ 初始位置、速度、加速度
    ├─ x(t)、y(t)或预置运动模型
    └─ 特殊情况与判定条件
    ↓
PhysicsEngine按时间计算状态
    ↓
PhysicsCanvas绘制轨迹、动画和实时数据
```

## 自定义运动函数

中栏 JSON 可使用：

```json
{
  "motion": {
    "kind": "custom",
    "x": "x0 + vx*t",
    "y": "y0 + 2*sin(omega*t)",
    "parameters": {"omega": 1.5}
  }
}
```

允许变量：`t, x0, y0, vx, vy, ax, ay` 和 `parameters` 中的数值。允许函数：`sin, cos, tan, sqrt, exp, log, abs, min, max`。表达式经过 AST 白名单校验，不会执行任意 Python 代码。

## 验证

```powershell
python -m py_compile main.py models.py data_interface.py ai_service.py physics_engine.py render_engine.py
python -m unittest discover -s tests -v
```

## 当前输出形式

当前采用“可编辑结构化 JSON + 物理判断文字 + 可交互二维动画”的组合。它既能用于课堂演示，也便于后续增加视频导出、旁白生成或把动画嵌入网页。对题目中没有给出的参数，规则解析会给演示默认值并提示核对；正式教学使用前应按原题修改 JSON 中的数值。

