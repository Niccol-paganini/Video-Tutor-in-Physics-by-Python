Video Tutor：基础物理碰撞与运动演示系统

Video Tutor 是一个使用 Python 开发的物理题可视化演示工具。系统接收自然语言题目或题目文件，通过离线规则或本地大模型识别运动物体、坐标系、运动函数和特殊条件，再生成可交互的二维运动动画。

项目主要面向圆周运动、抛体运动、物体碰撞等需要动态过程辅助理解的基础物理题。系统将题目解析、物理计算和动画渲染拆分为独立模块，便于继续增加新的物体类型、运动模型或大模型服务。

## 功能特点

- **多种题目输入方式**：支持直接输入文字，以及通过文件窗口读取 TXT、MD、CSV、JSON、DOCX；安装 `pypdf` 后可读取 PDF。
- **本地大模型接入**：通过 Ollama HTTP 接口调用本地模型，将自然语言题目转换为统一的场景 JSON。
- **离线解析模式**：未安装或未启动 Ollama 时，仍可通过关键词和预置规则生成常见物理场景。
- **结构化分析结果**：输出运动物体类型、坐标系、初始参数、`x(t)`/`y(t)`、特殊情况判断和讲解要点。
- **可编辑场景数据**：用户可以直接修改中栏 JSON，并重新应用到物理引擎和动画画布。
- **动态可视化**：展示运动轨迹、实时位置、速度分量、速度方向及当前运动阶段。
- **交互控制**：支持播放、暂停、重置、时间轴拖动和倍速播放。
- **结果导出**：支持导出结构化场景 JSON和当前动画帧。

## 支持的物理内容

### 基础图形

- 质点
- 圆形
- 长方形
- 正方形

### 运动模型

- 静止与匀速直线运动
- 匀变速直线运动
- 平抛、斜抛等抛体运动
- 匀速圆周运动
- 一维弹性或非完全弹性碰撞
- 自定义 `x(t)`、`y(t)` 运动函数

### 特殊场景

- **半圆轨道抛出**：物体先沿半圆轨道运动，到达端点后以切向速度进入抛体阶段。
- **滑块—木板恰好不冲出**：根据相对速度、相对加速度及最大相对位移判断滑块是否到达木板边缘。
- **一维碰撞**：根据质量、初速度和恢复系数计算碰撞时间及碰撞后速度。

## 系统流程

```text
题目文字或题目文件
        ↓
离线规则解析 / Ollama本地模型
        ↓
统一ProblemSpec场景JSON
        ├── 物体类型与基础图形
        ├── 初始位置、速度、加速度
        ├── 运动函数或预置运动模型
        └── 特殊情况及判断条件
        ↓
PhysicsEngine按时间计算物体状态
        ↓
PhysicsCanvas绘制轨迹、物体和实时信息
```

界面采用三栏结构：

1. **前端输入区**：输入题目或选择题目文件。
2. **AI结构化输出区**：查看、修改并应用场景 JSON，同时查看运动函数与特殊情况判断。
3. **动画演示区**：显示坐标系、轨迹、物体状态和播放控制。

## 快速运行

### 环境要求

- Python 3.10及以上版本
- Windows、macOS或Linux
- 核心功能只使用Python标准库

在项目目录执行：

```powershell
python main.py
```

Windows也可以直接双击：

```text
run.bat
```

程序启动后会自动加载圆周运动示例，无需配置大模型即可体验动画。

## 接入本地大模型

系统默认通过以下地址访问 Ollama：

```text
http://127.0.0.1:11434
```

使用步骤：

1. 安装并启动 Ollama。
2. 下载一个支持中文和 JSON 输出的模型，例如：

   ```powershell
   ollama pull qwen2.5:7b
   ```

3. 在界面顶部填写Ollama地址和模型名称。
4. 点击“检查模型”确认服务可用。
5. 输入题目并点击“调用本地AI”。

如果模型服务不可用，可以点击“规则解析（离线）”继续生成演示场景。

## 使用题目文件

点击界面顶部的“选择文件”可以载入：

```text
TXT / MD / CSV / JSON / DOCX / PDF
```

PDF读取需要安装可选依赖：

```powershell
python -m pip install pypdf
```

`examples` 文件夹中提供了可以直接载入的场景：

- `circular_motion.json`：匀速圆周运动
- `collision_1d.json`：一维完全弹性碰撞
- `semicircle_launch.json`：半圆轨道离轨抛出
- `block_plank.json`：滑块—木板恰好不冲出

## 结构化场景示例

下面是一个圆周运动物体的核心描述：

```json
{
  "problem_type": "circular",
  "objects": [
    {
      "id": "ball",
      "name": "圆周运动质点",
      "shape": "point",
      "initial_position": [3, 0],
      "motion": {
        "kind": "circular",
        "x": "cx + r*cos(omega*t + phase)",
        "y": "cy + r*sin(omega*t + phase)",
        "parameters": {
          "cx": 0,
          "cy": 0,
          "r": 3,
          "omega": 1.2,
          "phase": 0
        }
      }
    }
  ],
  "duration": 6
}
```

## 自定义运动函数

将 `motion.kind` 设置为 `custom` 后，可以直接输入运动函数：

```json
{
  "motion": {
    "kind": "custom",
    "x": "x0 + vx*t",
    "y": "y0 + 2*sin(omega*t)",
    "parameters": {
      "omega": 1.5
    }
  }
}
```

允许使用的基础变量包括：

```text
t, x0, y0, vx, vy, ax, ay
```

允许调用的数学函数包括：

```text
sin, cos, tan, sqrt, exp, log, abs, min, max
```

表达式会经过 AST 白名单校验，不允许执行导入、属性访问或其他任意 Python 代码。

## 项目结构

```text
├── main.py                  # 桌面界面、文件选择和动画控制
├── models.py                # ProblemSpec等统一数据模型
├── data_interface.py        # 文件读取、JSON校验和离线解析
├── ai_service.py            # Ollama HTTP接口及结构化提示词
├── ai接口.py                 # 兼容原工程模块名的AI入口
├── physics_engine.py        # 运动函数、碰撞和特殊场景计算
├── render_engine.py         # Tkinter动画画布
├── examples/                # 场景JSON示例
├── tests/                   # 核心逻辑自动化测试
├── requirements-optional.txt
└── run.bat
```

## 运行测试

语法检查：

```powershell
python -m py_compile main.py models.py data_interface.py ai_service.py physics_engine.py render_engine.py
```

运行自动化测试：

```powershell
python -m unittest discover -s tests -v
```

测试覆盖 JSON 协议、Ollama HTTP 调用、自定义函数安全性、圆周运动、完全弹性碰撞、半圆离轨连续性和滑块木板临界条件。

## 后续计划

- 增加更多高中及大学基础物理场景。
- 增加参数表单，减少直接编辑 JSON 的需要。
- 支持生成 GIF、MP4或网页动画。
- 增加速度、加速度和受力矢量图。
- 增加题目讲解文本与动画时间点联动。
- 支持替换为其他本地模型或外部大模型API。

## 使用说明

离线解析会为题目中未给出的物理量填入适合演示的默认值，并在分析区提示用户核对。正式教学或定量计算时，应以原题条件为准，检查结构化 JSON 中的质量、位置、速度、加速度和时间等参数。

