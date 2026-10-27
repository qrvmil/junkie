# Архитектура bimanual AgileX PIPER-X: Quest 3 → Sim/Real → Dataset → Policy → HITL

> Версия архитектуры: 24 августа 2026  
> Цель: единый стек для телеоперации, сбора данных, simulation, обучения, policy deployment и Human-in-the-Loop с минимальным количеством собственного кода.

---

# 1. Цели системы

Система должна поддерживать один и тот же пользовательский и ML-интерфейс для:

- двух AgileX PIPER-X в реальности;
- двух PIPER-X в EmbodiChain/DexSim;
- Isaac Sim / IsaacLab;
- MuJoCo;
- RoboTwin;
- других будущих симуляторов.

Источником действий может быть:

1. Meta Quest 3;
2. ML policy;
3. replay записанного эпизода;
4. комбинация policy + human intervention.

При этом не должны меняться:

- формат observation;
- формат action;
- названия камер;
- порядок joints;
- единицы измерения;
- dataset format;
- safety pipeline;
- HITL protocol.

Главная архитектурная идея:

> **Quest, policy и replay — это разные `ActionSource`, которые сходятся в один canonical `RobotAction`. Реальный робот и все симуляторы — разные `Backend`, которые получают этот же `RobotAction`.**

---

# 2. Итоговый выбор технологий

| Задача | Основная технология |
|---|---|
| Главный ML/control API | **LeRobot** |
| Quest 3 tracking/controllers | **NVIDIA Isaac Teleop** |
| Видео в Quest | **Televiz / Isaac Teleop `camera_viz` / CloudXR** |
| Quest → Cartesian intent | Isaac Teleop XRController |
| Cartesian → joints | **LeRobot Robot Processors + IK** |
| HITL / DAgger | **LeRobot HIL + небольшой Quest adapter** |
| Dataset | **LeRobotDataset** |
| Policy deployment | **LeRobot `lerobot-rollout`** |
| Большие VLA | LeRobot RTC / Async Policy Server |
| Основной research sim | **EmbodiChain / DexSim** |
| Isaac/PIPER reference sim | **LW-BenchHub / DoublePiper-Abs** |
| Benchmark | **RoboTwin 2.0** |
| Lightweight sim | **MuJoCo + Gymnasium wrapper** |
| Real PIPER-X reference | **Evo-RL** |
| Quest↔PIPER reference | **AgileX QuestArmTeleop** |
| Межпроцессный backend API | **ZeroMQ + простой Gym-like protocol** |
| Container orchestration | Docker Compose |

LeRobot уже имеет полноценные processor pipelines между teleoperator, dataset и robot и специально предполагает заменяемость этих компонентов.

---

# 3. Высокоуровневая архитектура

```text
                              ┌─────────────────────────┐
                              │      META QUEST 3       │
                              │                         │
                              │ Controllers     Display │
                              └──────┬───────────▲──────┘
                                     │           │
                              tracking│           │video
                                     │           │
                         ┌───────────▼───────────┴──────┐
                         │       NVIDIA ISAAC TELEOP    │
                         │                              │
                         │ XRController   CloudXR       │
                         │ TeleopSession  Televiz       │
                         └──────────────┬───────────────┘
                                        │
                                  TeleopIntent
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │      CONTROL RUNTIME         │
                         │                              │
                         │        LeRobot 0.6.x         │
                         │                              │
                         │ Quest Processor              │
                         │ IK / retargeting             │
                         │ Policy runtime               │
                         │ ActionMux / HITL             │
                         │ Safety                       │
                         │ Dataset Recorder             │
                         └──────────────┬───────────────┘
                                        │
                                  RobotAction
                                        │
                           BackendClient / RPC
                                        │
             ┌──────────────────────────┼────────────────────────┐
             │                          │                        │
             ▼                          ▼                        ▼
     ┌───────────────┐          ┌───────────────┐       ┌──────────────┐
     │  EmbodiChain  │          │  Isaac/LW     │       │  RoboTwin   │
     │               │          │  BenchHub     │       │              │
     │ DexSim        │          │ DoublePiper   │       │ SAPIEN       │
     │ PIPER-X       │          │ IsaacLab      │       │ PIPER/Aloha  │
     └───────┬───────┘          └───────┬───────┘       └──────┬───────┘
             │                          │                      │
             └──────────────────────────┼──────────────────────┘
                                        │
                                        │
                   ┌────────────────────┼────────────────────┐
                   │                    │                    │
                   ▼                    ▼                    ▼
               MuJoCo             Mock Backend          REAL PIPER-X
                                                         Evo-RL /
                                                         Piper driver
```

Observation идёт по той же схеме обратно:

```text
Backend
   │
   ├── joint state
   ├── gripper state
   ├── RGB cameras
   ├── timestamps
   └── task info
          │
          ▼
 canonical Observation
          │
     ┌────┴───────┐
     ▼            ▼
 Dataset        Policy
 Recorder       inference
     │
     └──────────────► Televiz ──► Quest
```

---

# 4. Почему backend'ы должны быть отдельными процессами

Не стоит пытаться сделать:

```text
one-python-env/
├── LeRobot
├── IsaacSim
├── RoboTwin
├── EmbodiChain
├── Evo-RL
└── MuJoCo
```

У этих проектов уже сейчас конфликтуют версии Python, Torch, NumPy и LeRobot.

Например, EmbodiChain сейчас требует `lerobot>=0.4.4,<0.5`, тогда как актуальный LeRobot 0.6.x использует Python ≥3.12.  

Evo-RL тоже построен вокруг LeRobot 0.4.4. 

Поэтому правильная граница:

```text
control-runtime
      │
      │ RPC
      ▼
backend-runtime
```

Все backend'ы реализуют одинаковый интерфейс независимо от своих внутренних зависимостей.

---

# 5. Canonical contracts

Это самый важный кусок архитектуры.

До написания интеграций нужно заморозить три структуры:

```text
TeleopIntent
RobotAction
RobotObservation
```

---

## 5.1 TeleopIntent

Это то, что приходит от Quest.

```yaml
TeleopIntent:
  timestamp_ns: int

  left:
    position: [x, y, z]       # meters
    quaternion: [x, y, z, w]
    gripper: float            # 0..1
    clutch: bool

  right:
    position: [x, y, z]
    quaternion: [x, y, z, w]
    gripper: float
    clutch: bool

  events:
    takeover: bool
    pause: bool
    reset: bool
    stop: bool
```

Quest action **не должен напрямую становиться action датасета**.

---

# 5.2 Canonical RobotAction

После clutch, frame transform, safety и IK получаем:

```yaml
RobotAction:
  timestamp_ns: int

  left:
    q_target: [q1, q2, q3, q4, q5, q6]  # radians
    gripper: float                       # 0..1

  right:
    q_target: [q1, q2, q3, q4, q5, q6]
    gripper: float

  source:
    POLICY | HUMAN | REPLAY
```

Итого основное action пространство:

```text
6 + 1 + 6 + 1 = 14 dimensions
```

Это действие получают **все backend'ы**.

---

# 5.3 Canonical Observation

```yaml
RobotObservation:
  timestamp_ns: int

  state:
    left:
      q: [6]
      qvel: [6]          # optional
      gripper: float

    right:
      q: [6]
      qvel: [6]
      gripper: float

  images:
    front: RGB
    left_wrist: RGB
    right_wrist: RGB

  task:
    instruction: str

  backend:
    name: str
    episode_id: int

  info:
    is_success: bool
    is_failure: bool
```

Канонический `observation.state` для первой версии:

```text
left.q[6]
left.gripper
right.q[6]
right.gripper

= 14 values
```

---

# 5.4 Единицы и conventions

Нельзя позволять симуляторам самостоятельно определять эти вещи.

```yaml
units:
  translation: meter
  angle: radian
  gripper: normalized_0_1

orientation:
  quaternion: xyzw
  handedness: right

joint_order:
  left:
    - joint1
    - joint2
    - joint3
    - joint4
    - joint5
    - joint6

  right:
    - joint1
    - joint2
    - joint3
    - joint4
    - joint5
    - joint6
```

Нужен единственный файл:

```text
configs/embodiments/piper_x_bimanual_v1.yaml
```

Все backend'ы обязаны адаптироваться **к нему**, а не наоборот.

---

# 5.5 Coordinate frames

Минимальный набор:

```text
world
├── left_base
│   └── left_ee
│
├── right_base
│   └── right_ee
│
└── xr_anchor
    ├── left_controller
    └── right_controller
```

В момент clutch:

```text
T_controller(t0)
T_ee(t0)
```

сохраняем относительный anchor.

После этого:

```text
controller delta
        ↓
desired EE delta
```

а не absolute Quest room coordinates.

Это предотвращает скачок робота при takeover/re-engage. Именно такой clutch/rebase pattern уже используется в интеграции Isaac Teleop → LeRobot.

---

# 6. Частоты

Я бы первоначально зафиксировал:

```yaml
xr_tracking_hz: native       # 72/90 Hz Quest
camera_capture_hz: 30

policy_hz: 25
dataset_hz: 25

robot_command_hz: 50
```

То есть:

```text
policy action @25 Hz
        │
   interpolation
        ▼
robot command @50 Hz
```

Почему 25 Hz:

- удобно для VLA;
- совпадает с типичным RoboTwin cadence;
- уменьшает нагрузку на camera/data pipeline;
- LeRobot умеет повышать частоту команд через interpolation/RTC.

Если позже измерения покажут необходимость 30 Hz — меняется одним profile config.

---

# 7. Блок A — Control Runtime

## Технология

**LeRobot 0.6.x**

## За что отвечает

```text
Control Runtime
├── teleoperator abstraction
├── robot/policy processors
├── action representations
├── dataset
├── policy rollout
├── HITL
├── RTC
└── inference API
```

Он **не должен знать**, является backend реальным PIPER или симулятором.

LeRobot processors как раз предназначены для построения:

```text
Teleoperator
    ↓
dataset action
    ↓
robot action
```

и позволяют менять teleoperator/robot без переписывания glue logic.

**Setup tutorial:**  
[LeRobot — Installation](https://huggingface.co/docs/lerobot/main/en/installation?utm_source=chatgpt.com)

**Architecture/tutorial:**  
[Processors for Robots and Teleoperators](https://huggingface.co/docs/lerobot/processors_robots_teleop?utm_source=chatgpt.com)

---

# 8. Блок B — Meta Quest 3 input

## Технология

**NVIDIA Isaac Teleop**

Используем:

```text
XRController
TeleopSession
CloudXR
ControllerTransform
```

Isaac Teleop поддерживает Quest и создавался именно как единый device/retargeting stack для sim и real.

## За что отвечает

```text
Quest controllers
       ↓
tracking
       ↓
controller pose
       ↓
buttons / triggers / grip
       ↓
TeleopIntent
```

## Что НЕ пишем сами

- OpenXR;
- Quest application;
- controller tracking;
- WebRTC/WebXR;
- CloudXR protocol;
- controller pose reader.

Для Quest можно использовать готовый WebXR client в браузере.

**Tutorial:**  
[Isaac Teleop — Quick Start / Quest / CloudXR](https://nvidia.github.io/IsaacTeleop/main/getting_started/quick_start.html?utm_source=chatgpt.com)

**LeRobot integration tutorial:**  
[LeRobot — Isaac Teleop XR Controller](https://huggingface.co/docs/lerobot/main/isaac_teleop?utm_source=chatgpt.com)

---

# 9. Блок C — камеры → Quest

## Технология

**Televiz + `camera_viz`**

## За что отвечает

```text
front camera ───────────┐
left wrist camera ──────┼──► Televiz ─► CloudXR ─► Quest
right wrist camera ─────┘
```

Поддерживаются несколько camera planes, XR placement и отдельный robot→workstation RTP mode.

`camera_viz` умеет:

- video replay;
- V4L2/UVC;
- OAK-D;
- ZED;
- RTP/H.264;
- несколько камер;
- Quest XR output.

## Важный design choice

Есть **два camera path**.

### Training path

```text
camera
  ↓
RobotObservation
  ↓
LeRobotDataset
```

### Operator path

```text
camera
  ↓
Televiz
  ↓
Quest
```

Они используют тот же физический источник, но операторский stream не обязан ждать policy/dataset tick.

**Tutorial:**  
[Isaac Teleop — Camera Streaming](https://nvidia.github.io/IsaacTeleop/main/references/camera_streaming.html?utm_source=chatgpt.com)

**Televiz API:**  
[Isaac Teleop — Televiz](https://nvidia.github.io/IsaacTeleop/main/getting_started/televiz.html?utm_source=chatgpt.com)

---

# 10. Блок D — Quest → PIPER retargeting

## Технология

**LeRobot RobotProcessorPipeline**

Цепочка:

```text
XR controller pose
        ↓
MapXRControllerAction
        ↓
Clutch / reference
        ↓
EE bounds
        ↓
IK
        ↓
joint limits
        ↓
RobotAction[14]
```

LeRobot уже содержит готовые abstractions:

```text
EEBoundsAndSafety
InverseKinematicsEEToJoints
ForwardKinematicsJointsToEE
```



## Что нужно заменить для PIPER

Только:

```text
URDF
joint names
EE link name
joint limits
workspace bounds
base transforms
```

Сам IK framework писать не нужно.

**Tutorial:**  
[LeRobot — Processors for Robots and Teleoperators](https://huggingface.co/docs/lerobot/processors_robots_teleop?utm_source=chatgpt.com)

---

# 11. Блок E — официальный PIPER/Quest reference

## Технология

**AgileX QuestArmTeleop**

Это не основной runtime.

Используем как **golden reference** для:

- PIPER-X URDF;
- controller ↔ EE frame alignment;
- joint mapping;
- Quest buttons;
- dual-arm conventions;
- проверенного IK setup.

Проект официально поддерживает Quest 2/3/3S → PIPER-X и имеет готовый `arm_ik_pose_node.piper_x.yaml`. 

## Зачем он нужен

Если наш generic LeRobot IK движет руку иначе, чем официальный AgileX implementation, сначала сравниваем frame/config с QuestArmTeleop.

**Setup/reference:**  
[AgileX QuestArmTeleop](https://github.com/agilexrobotics/QuestArmTeleop?utm_source=chatgpt.com)

---

# 12. Блок F — ActionMux / Human-in-the-Loop

```text
policy_action ────────────┐
                          │
human_action ─────────────┼──► ActionMux ─► safety ─► backend
                          │
replay_action ────────────┘
```

## Состояния

```text
AUTONOMOUS
PAUSED
HUMAN_LEFT
HUMAN_RIGHT
HUMAN_BOTH
STOPPED
```

Для bimanual системы полезно разрешить takeover одной руки:

```text
left  = policy
right = human
```

или наоборот.

---

# 12.1 HIL protocol

```text
POLICY
   ↓
imminent failure
   ↓
PAUSE
   ↓
HUMAN TAKEOVER
   ↓
RECOVERY
   ↓
CORRECTION
   ↓
RETURN TO POLICY
```

LeRobot официально поддерживает DAgger/HG-DAgger/RaC-style HIL и умеет записывать human corrections вместе с autonomous rollout.

**Tutorial:**  
[LeRobot — Human-in-the-Loop Data Collection](https://huggingface.co/docs/lerobot/hil_data_collection?utm_source=chatgpt.com)

---

# 12.2 Единственный существенный gap: Quest HIL adapter

Стандартный LeRobot DAgger сейчас предполагает motorized leader teleoperator, которому можно отправить pose feedback перед takeover.

Quest физически перемещать не нужно.

Поэтому для Quest нужен маленький adapter:

```text
Quest takeover button
        ↓
pause policy
        ↓
capture current robot EE
        ↓
capture current Quest controller pose
        ↓
rebase clutch
        ↓
HUMAN control
```

Это должно быть порядка одной специализированной integration layer, а не собственного HIL framework.

Isaac Teleop уже имеет control state machine с:

```text
STOPPED
PAUSED
RUNNING
```

и fail-safe при потере controller inputs.

**Tutorial:**  
[Isaac Teleop — Control State Machine](https://nvidia.github.io/IsaacTeleop/main/getting_started/teleop_control_state_machine.html?utm_source=chatgpt.com)

---

# 13. Блок G — Safety

Safety стоит **после ActionMux**:

```text
Quest ─────┐
Policy ────┼──► ActionMux ─► SAFETY ─► robot
Replay ────┘
```

То есть у человека и policy одинаковые ограничения.

## Safety pipeline

```text
command
  ↓
finite / NaN check
  ↓
joint position limits
  ↓
max Δq / tick
  ↓
velocity limits
  ↓
workspace bounds
  ↓
IK success
  ↓
self-collision / inter-arm collision
  ↓
watchdog
  ↓
backend
```

LeRobot processors прямо предполагают safety constraints как processing step.

## Safety обязательно дублируется в real backend

Даже если control-runtime умер:

```text
no heartbeat for N ms
        ↓
PIPER backend
        ↓
hold / controlled stop
```

Нельзя зависеть только от Python-процесса policy.

---

# 14. Блок H — Dataset

## Формат

**LeRobotDataset**

Основной frame:

```yaml
observation.state: [14]

observation.images.front: image
observation.images.left_wrist: image
observation.images.right_wrist: image

action: [14]

task: "put object in box"
```

LeRobotDataset уже поддерживает state/action/video и является общим форматом для LeRobot policy stack.

**Tutorial:**  
[LeRobotDataset v3.0](https://huggingface.co/docs/lerobot/lerobot-dataset-v3?utm_source=chatgpt.com)

---

# 14.1 HITL metadata

Дополнительно сохраняем:

```yaml
action.policy: [14]
action.human: [14]
action.executed: [14]

annotation.control_source:
  POLICY | HUMAN_LEFT | HUMAN_RIGHT | HUMAN_BOTH

annotation.intervention: bool
annotation.ik_success: bool

backend.name: str
```

Главным training target первоначально делаем:

```text
action.executed
```

а не сырой controller intent.

---

# 14.2 Temporal semantics

Каждый frame:

```text
obs_t
  ↓
choose action_t
  ↓
execute action_t
  ↓
obs_t+1
```

Dataset хранит causal pair:

```text
(obs_t, action_t)
```

а не случайную смесь `obs_{t+1}` и `action_t`.

---

# 15. Блок I — Policy Runtime

Основной interface:

```python
action = policy.select_action(observation)
```

После policy:

```text
raw policy action
      ↓
PolicyProcessor
      ↓
canonical RobotAction
```

Policy может быть:

```text
ACT
Diffusion Policy
SmolVLA
Pi0 / Pi0.5
GR00T
другая VLA
```

LeRobot `lerobot-rollout` уже является единым deployment interface для policy rollout.

**Tutorial:**  
[LeRobot — Policy Deployment / lerobot-rollout](https://huggingface.co/docs/lerobot/main/inference?utm_source=chatgpt.com)

---

# 15.1 Большие VLA

Для медленной модели:

```text
robot loop ───────────────► execution
     ▲
     │ action chunks
     │
Policy Server
```

Используем либо:

- RTC;
- LeRobot Async Inference;
- отдельный model server.

LeRobot уже поддерживает decoupled `PolicyServer` / `RobotClient`.

**Tutorial:**  
[LeRobot — Asynchronous Inference](https://huggingface.co/docs/lerobot/en/async?utm_source=chatgpt.com)

---

# 16. Блок J — Backend API

Это основное собственное инфраструктурное API.

Минимальный interface:

```python
class RobotBackend:
    def describe() -> BackendDescription: ...
    def reset() -> RobotObservation: ...
    def step(action: RobotAction) -> StepResult: ...
    def close() -> None: ...
```

`StepResult`:

```yaml
observation: RobotObservation
reward: float
terminated: bool
truncated: bool
info:
  is_success: bool
```

Это практически Gymnasium API.

Gymnasium определяет тот же базовый контракт через `reset()` / `step()`.

LeRobot benchmark adapters тоже строятся вокруг Gym environments.

**Tutorial:**  
[Gymnasium — Create a Custom Environment](https://gymnasium.farama.org/main/introduction/create_custom_env/?utm_source=chatgpt.com)

**LeRobot-side tutorial:**  
[LeRobot — Adding a New Benchmark](https://huggingface.co/docs/lerobot/main/adding_benchmarks?utm_source=chatgpt.com)

---

# 16.1 Transport

Для первой версии:

**ZeroMQ REQ/REP + multipart messages.**

```text
control-runtime        backend
     │                    │
     │── STEP(action) ───►│
     │                    │
     │◄── observation ────│
```

Добавляем:

```text
seq_id
timestamp
timeout
heartbeat
protocol_version
```

Не нужно сразу писать gRPC/protobuf service.

**Tutorial:**  
[ZeroMQ — Request/Reply Patterns](https://zguide.zeromq.org/docs/chapter3/?utm_source=chatgpt.com)

---

# 17. Блок K — EmbodiChain backend

## Роль

**Основной research/data-generation simulator.**

```text
Backend RPC
    ↓
EmbodiedEnv.step(action)
    ↓
ActionManager
    ↓
DexSim
```

EmbodiChain уже предоставляет Gymnasium-compatible `EmbodiedEnv`, `ActionManager`, `ObservationManager`, `DatasetManager` и vectorized GPU simulation.

**Getting started:**  
[EmbodiChain — Tutorials](https://dexforce.github.io/EmbodiChain/v0.2.3/tutorial/index.html?utm_source=chatgpt.com)

**Environment tutorial:**  
[EmbodiChain — Creating a Modular Environment](https://dexforce.github.io/EmbodiChain/v0.2.3/tutorial/modular_env.html?utm_source=chatgpt.com)

---

# 17.1 PIPER action mapping внутри EmbodiChain

Для нашего canonical joint action достаточно:

```text
QposTerm
```

EmbodiChain уже имеет:

```text
QposTerm
DeltaQposTerm
EefPoseTerm
QvelTerm
QfTerm
```



**Tutorial:**  
[EmbodiChain — Action Functors](https://dexforce.github.io/EmbodiChain/v0.2.3/overview/gym/action_functors.html?utm_source=chatgpt.com)

---

# 17.2 EmbodiChain dataset generator

Для интерактивной работы dataset пишет внешний LeRobot control-runtime.

Но для:

```text
100 / 1000 parallel envs
scripted expert
domain randomization
```

используем native:

```text
AsyncLeRobotRecorder
```

EmbodiChain умеет непосредственно экспортировать LeRobot-format demonstrations.

**Tutorial:**  
[EmbodiChain — Dataset Functors / LeRobotRecorder](https://dexforce.github.io/EmbodiChain/v0.2.3/overview/gym/dataset_functors.html?utm_source=chatgpt.com)

---

# 18. Блок L — Isaac / LW-BenchHub backend

LW-BenchHub уже имеет:

```yaml
robot: DoublePiper-Abs
teleop_device: vr-controller
enable_cameras: true
```



И проект заявляет:

- AgileX Piper;
- Meta Quest;
- teleoperation;
- dataset collection;
- policy deployment;
- IsaacLab environment.



Это очень полезный **golden simulator**.

## Использование

Не обязательно делать его главным teleop framework.

Используем его:

1. как reference, что dual Piper + VR работает;
2. как Isaac backend;
3. как дополнительную sim→real validation среду.

**Setup/tutorial:**  
[LW-BenchHub Documentation](https://docs.lightwheel.net/lw_benchhub?utm_source=chatgpt.com)

**Repo:**  
[LightwheelAI/LW-BenchHub](https://github.com/LightwheelAI/LW-BenchHub?utm_source=chatgpt.com)

---

# 19. Блок M — RoboTwin backend

RoboTwin остаётся benchmark, а не control framework.

LeRobot уже имеет официальный:

```bash
--env.type=robotwin
```

и унифицированный evaluation flow.

## Роль

```text
policy
  ↓
canonical processor
  ↓
RoboTwin
  ↓
success rate
```

При наличии нашего PIPER embodiment сохраняем те же semantic camera/action keys.

Upstream benchmark по умолчанию использует Aloha-AgileX 14-DOF и три камеры, поэтому custom PIPER config должен оставаться отдельным профилем.

**Tutorial:**  
[LeRobot — RoboTwin 2.0](https://huggingface.co/docs/lerobot/en/robotwin?utm_source=chatgpt.com)

---

# 20. Блок N — MuJoCo backend

MuJoCo здесь нужен как:

- быстрый lightweight simulator;
- unit/integration testing;
- IK/control debugging;
- быстрые CI rollouts.

Используем native Python `mujoco` bindings.

Поверх существующего env делаем тонкий:

```text
Gymnasium wrapper
```

который возвращает canonical observation/action.

**MuJoCo tutorial:**  
[MuJoCo — Python Bindings](https://mujoco.readthedocs.io/en/latest/python.html?utm_source=chatgpt.com)

**Gym wrapper tutorial:**  
[Gymnasium — Custom Environment](https://gymnasium.farama.org/main/introduction/create_custom_env/?utm_source=chatgpt.com)

---

# 21. Блок O — Real PIPER-X backend

## Первоначальная реализация

Используем код из **Evo-RL** как reference/backend runtime.

У них уже есть:

```text
piperx_follower
bi_piperx_follower
piperx_leader
bi_piperx_leader
```

и реальный AgileX PiPER/PiPER-X pipeline. 

Для Quest leader arms не нужны.

Нам нужен только:

```text
bi_piperx_follower
```

Backend получает canonical `[14]` action и отправляет команды двум arms.

**Setup/tutorial:**  
[Evo-RL — AgileX PiPER/PiPER-X setup](https://github.com/MINT-SJTU/Evo-RL?utm_source=chatgpt.com#agilex-piper-setup)

---

# 21.1 Real backend safety

Этот backend обязан независимо реализовать:

```text
CAN state monitoring
joint limits
command timeout
watchdog
hold
emergency stop handling
```

То есть даже если:

```text
LeRobot process crashed
network disappeared
Quest disconnected
policy hung
```

backend перестаёт принимать движение.

---

# 22. Docker/process layout

```text
docker-compose.yml

services:

  control:
    Python 3.12
    LeRobot 0.6.x
    Isaac Teleop
    Televiz

  backend-embodichain:
    EmbodiChain
    DexSim

  backend-isaac:
    IsaacLab
    LW-BenchHub

  backend-robotwin:
    RoboTwin
    Python 3.10

  backend-mujoco:
    MuJoCo

  backend-piper:
    Evo-RL / Piper driver
    LeRobot 0.4.4 compatible env

  policy-server:
    optional
    GR00T / large VLA
```

Обычно активен один backend:

```bash
BACKEND=embodichain
```

или:

```bash
BACKEND=piper-real
```

а Quest/policy/data code не меняется.

---

# 23. Рекомендуемая структура репозитория

```text
piper-platform/
│
├── docs/
│   └── ARCHITECTURE.md
│
├── contracts/
│   ├── action.py
│   ├── observation.py
│   ├── backend.py
│   └── protocol.py
│
├── control_runtime/
│   ├── main.py
│   ├── quest/
│   ├── processors/
│   ├── hitl/
│   ├── safety/
│   └── recorder/
│
├── backends/
│   ├── mock/
│   ├── embodichain/
│   ├── isaac/
│   ├── mujoco/
│   ├── robotwin/
│   └── piper_real/
│
├── configs/
│   ├── embodiment/
│   │   └── piper_x_bimanual_v1.yaml
│   │
│   ├── cameras/
│   │   └── three_camera.yaml
│   │
│   ├── safety/
│   │   └── piper_x.yaml
│   │
│   └── backends/
│
├── tests/
│   ├── contract/
│   ├── backend/
│   ├── processors/
│   └── hitl/
│
├── docker/
│   ├── control/
│   ├── embodichain/
│   ├── isaac/
│   ├── robotwin/
│   └── piper/
│
└── docker-compose.yml
```

---

# 24. Что реально придётся написать самим

При правильной декомпозиции собственный framework не нужен.

## Нужно

### 1. Canonical contract

```text
RobotAction
RobotObservation
BackendDescription
```

Очень небольшой слой.

### 2. Backend RPC

```text
describe()
reset()
step()
close()
```

### 3. Quest → PIPER config

В основном:

```text
URDF
frames
motor names
bounds
```

а не собственный IK.

### 4. Quest HITL adapter

Чтобы связать:

```text
LeRobot DAgger semantics
+
Isaac Teleop clutch
```

### 5. Backend wrappers

Каждый обычно очень тонкий:

```python
env.step(action)
```

## Не пишем

```text
VR tracking
OpenXR
Quest application
video streaming protocol
IK solver
dataset format
policy loader
DAgger algorithm
RTC
camera drivers
sim engine
robot driver
benchmark runner
```

---

# 25. План настройки ДО приезда роботов

Главное правило:

> Не ждать hardware. К приезду PIPER весь стек выше `backend-piper-real` должен уже работать end-to-end.

---

# Итерация 0 — Freeze contracts

## Сделать

Создать:

```text
piper_x_bimanual_v1.yaml
RobotAction
RobotObservation
Backend API
```

Зафиксировать:

- joint order;
- units;
- quaternion convention;
- camera names;
- control FPS;
- gripper convention;
- timestamps.

## Acceptance criterion

Один mock action:

```text
[14]
```

проходит serialize → deserialize без изменения.

---

# Итерация 1 — Mock backend

Сделать простейший backend без physics:

```text
action_t
   ↓
q_{t+1} = action_t
```

С fake RGB cameras.

## Проверяем

```text
control runtime
RPC
observation
action
reset
timeouts
recording
```

## Результат

Вся архитектура работает вообще без simulator.

---

# Итерация 2 — Quest 3 standalone

Запустить Isaac Teleop.

Пока вместо robot:

```text
Quest controller
      ↓
print pose
```

## Проверяем

- оба controller;
- position;
- orientation;
- trigger;
- grip;
- A/B/X/Y;
- tracking loss;
- reconnect.

## Acceptance criterion

При потере controller:

```text
RUNNING → STOPPED
```

без ручного вмешательства.

**Tutorial:**  
[Isaac Teleop Quick Start](https://nvidia.github.io/IsaacTeleop/main/getting_started/quick_start.html?utm_source=chatgpt.com)

---

# Итерация 3 — Видео в Quest без робота

Использовать:

```text
camera_viz
```

сначала с bundled video replay.

Потом:

```text
USB webcam
```

## Проверяем

```text
front
left_wrist
right_wrist
```

как три XR plane.

## Acceptance criterion

Quest одновременно:

```text
отдаёт controller tracking
и
принимает video
```

через одну XR session.

Isaac Teleop прямо поддерживает sharing OpenXR session между Televiz и TeleopSession.

---

# Итерация 4 — Golden reference: LW-BenchHub DoublePiper

До разработки собственного bridge полезно поднять уже готовый:

```yaml
robot: DoublePiper-Abs
teleop_device: vr-controller
```



## Цель

Получить подтверждение:

```text
VR
  ↓
dual Piper
  ↓
task
```

на существующем open-source implementation.

Это будет baseline, с которым сравниваем свою кинематику.

---

# Итерация 5 — EmbodiChain standalone

Поднять:

```text
EmbodiedEnv
PIPER-X
camera
QposTerm
```

Сначала управлять random/scripted actions.

## Проверяем

- joint names;
- q limits;
- gripper;
- cameras;
- physics;
- reset.

**Tutorial:**  
[EmbodiChain — Simulating a Robot](https://dexforce.github.io/EmbodiChain/v0.2.3/tutorial/robot.html?utm_source=chatgpt.com)

---

# Итерация 6 — EmbodiChain RPC backend

```text
control-runtime
      │
      │ RobotAction
      ▼
EmbodiChain server
      │
      │ Observation
      ▼
control-runtime
```

## Acceptance criterion

10k sequential steps:

```text
reset
step
step
...
```

без:

- shape mismatch;
- stale frame;
- timestamp reversal;
- memory growth.

---

# Итерация 7 — Quest → EmbodiChain PIPER

Теперь соединяем:

```text
Quest
  ↓
Isaac Teleop
  ↓
LeRobot Processor
  ↓
IK
  ↓
RobotAction
  ↓
EmbodiChain
```

Это первый настоящий end-to-end MVP.

## Проверяем

- left/right correspondence;
- EE orientation;
- gripper;
- clutch;
- no jump after clutch;
- workspace bounds.

---

# Итерация 8 — Dataset recording

Во время Quest teleop пишем:

```text
LeRobotDataset
```

Потом replay:

```text
dataset action
      ↓
EmbodiChain
```

## Acceptance criterion

Replay должен визуально воспроизводить оригинальную демонстрацию.

Если replay расходится — сначала чинить action semantics, а не начинать обучение.

---

# Итерация 9 — первая policy

Не нужно сразу брать GR00T.

Для проверки инфраструктуры достаточно:

```text
ACT / Diffusion Policy / SmolVLA
```

Цель не SOTA, а доказать:

```text
Quest data
   ↓
LeRobotDataset
   ↓
training
   ↓
policy
   ↓
same RobotAction
   ↓
same backend
```

## Acceptance criterion

Переключение:

```text
SOURCE=quest
```

на:

```text
SOURCE=policy
```

не меняет backend code.

---

# Итерация 10 — HITL в simulation

Теперь:

```text
policy drives Piper
        ↓
Quest takeover
        ↓
human recovery
        ↓
return to policy
```

Сначала только `HUMAN_BOTH`.

Потом:

```text
HUMAN_LEFT
HUMAN_RIGHT
```

## Acceptance criterion

Takeover:

- не вызывает joint jump;
- не reset'ит episode;
- помечается в dataset;
- policy после возврата продолжает с текущего состояния.

---

# Итерация 11 — RoboTwin backend

После того как canonical contract уже стабилен.

```text
same policy
same dataset processor
same action semantics
        ↓
RoboTwin
```

Здесь уже можно начать benchmark work.

---

# Итерация 12 — MuJoCo backend

Нужен главным образом для:

- CI;
- fast tests;
- debugging;
- deterministic regression.

Каждый commit можно тестировать:

```text
Mock
MuJoCo
```

без GPU simulator.

---

# Итерация 13 — подготовить real backend ДО приезда рук

Даже без hardware можно подготовить:

```text
backend-piper Docker image
Evo-RL dependencies
CAN setup scripts
udev rules
configuration parser
watchdog
fake CAN mode
```

Также заранее определить:

```yaml
left_can_serial: ...
right_can_serial: ...
```

как placeholders.

Когда роботы приедут, меняются только IDs.

---

# 26. План ПОСЛЕ приезда роботов

Не начинать сразу с dual-arm Quest.

---

# Real Stage 1 — одна рука без Quest

```text
CLI
 ↓
tiny q delta
 ↓
PIPER
```

С жёсткими velocity limits.

Проверить:

- encoder signs;
- joint order;
- gripper;
- emergency stop;
- watchdog.

---

# Real Stage 2 — одна рука + LeRobot backend

```text
control-runtime
      ↓
real backend
      ↓
one Piper
```

Сначала scripted action.

---

# Real Stage 3 — Quest + одна рука

```text
Quest
  ↓
IK
  ↓
one Piper
```

Использовать официальный QuestArmTeleop как frame/reference baseline.

---

# Real Stage 4 — две руки

Только после каждой руки отдельно.

```text
Quest left  → Piper left
Quest right → Piper right
```

Сначала запрещаем crossing workspace:

```text
left arm:
    x < center

right arm:
    x > center
```

Потом постепенно расширяем workspace.

---

# Real Stage 5 — камеры

Подключить:

```text
front
left_wrist
right_wrist
```

Проверить одновременно:

```text
Dataset
+
Quest streaming
```

---

# Real Stage 6 — первые реальные demonstrations

```text
Quest
 ↓
real Piper
 ↓
LeRobotDataset
```

Сравнить schema с simulation dataset:

```text
keys identical
shapes identical
units identical
action order identical
```

Это главный sim→real contract test.

---

# Real Stage 7 — policy rollout

Сначала:

```text
very low speed
small workspace
human ready
```

Policy получает тот же Observation, который получала в simulation.

---

# Real Stage 8 — HITL

Финальная схема:

```text
                  ┌──────────── Policy
                  │
                  ▼
Quest ───────► ActionMux
                  │
                  ▼
                Safety
                  │
                  ▼
             Dual PIPER-X
```

Operator может:

```text
observe
take over
recover
correct
return control
```

---

# 27. Acceptance tests перед real policy rollout

До autonomous real rollout должны проходить все пункты:

```text
[ ] Quest tracking loss → STOPPED
[ ] Backend timeout → HOLD/STOP
[ ] NaN action rejected
[ ] joint-limit violation rejected
[ ] excessive Δq rejected
[ ] IK failure rejected
[ ] clutch engage causes no jump
[ ] left/right arm cannot swap
[ ] dataset action order validated
[ ] camera identities validated
[ ] replay reproduces demo
[ ] policy→sim works
[ ] HITL→sim works
[ ] physical E-stop tested
```

---

# 28. Приоритет работ прямо сейчас

Поскольку физические руки ещё не приехали, порядок я бы сделал именно таким:

```text
1. Freeze canonical Action/Observation
        ↓
2. Mock backend
        ↓
3. Quest + Isaac Teleop
        ↓
4. Televiz / camera replay → Quest
        ↓
5. LW-BenchHub DoublePiper reference
        ↓
6. EmbodiChain PIPER backend
        ↓
7. Quest → EmbodiChain end-to-end
        ↓
8. LeRobotDataset record/replay
        ↓
9. Policy → EmbodiChain
        ↓
10. HITL → EmbodiChain
        ↓
11. RoboTwin
        ↓
12. MuJoCo CI backend
        ↓
13. Pre-build real PIPER backend
        ↓
        ROBOTS ARRIVE
        ↓
14. single Piper
        ↓
15. dual Piper
        ↓
16. cameras
        ↓
17. Quest teleop
        ↓
18. real dataset
        ↓
19. policy
        ↓
20. HITL
```

---

# 29. Что считать MVP

Первый meaningful MVP **не требует физических роботов**.

MVP готов, когда работает:

```text
Meta Quest 3
      │
      ├──── controller tracking
      │
      ▼
Isaac Teleop
      │
      ▼
LeRobot Processor
      │
      ▼
Bimanual RobotAction
      │
      ▼
EmbodiChain / Double Piper
      │
      ▼
three camera observations
      │
      ├────► Quest via Televiz
      │
      └────► LeRobotDataset
```

и можно нажатием одного config switch заменить:

```text
Quest
```

на:

```text
Policy
```

без изменения backend.

Следующий milestone:

```text
Policy → simulated PIPER
     ↓
Quest intervention
     ↓
LeRobot HIL dataset
```

Если эти два сценария готовы до приезда роботов, то hardware integration превращается преимущественно в подключение нового backend'а, а не в проектирование системы с нуля.

---

# 30. Финальная граница ответственности

```text
┌────────────────────────────────────────────────────┐
│                    LeRobot                         │
│                                                    │
│ observations / actions / policies / dataset / HITL │
└──────────────────────┬─────────────────────────────┘
                       │
                 canonical contract
                       │
┌──────────────────────▼─────────────────────────────┐
│                 Backend API                        │
│            reset / step / observation              │
└─────────┬────────────┬────────────┬────────────┬────┘
          │            │            │            │
          ▼            ▼            ▼            ▼
     EmbodiChain     Isaac       RoboTwin      Real
       DexSim       LW-Bench       SAPIEN     PIPER-X
```

А Quest расположен ортогонально:

```text
Quest
  ↓
Isaac Teleop
  ↓
LeRobot Teleoperator
```

Именно такое разделение позволяет одновременно иметь:

- минимальное количество собственного кода;
- одинаковый sim/real control path;
- единый dataset;
- заменяемые policies;
- Human-in-the-Loop;
- разные simulator stacks;
- отсутствие зависимости всей системы от одного robotics framework.