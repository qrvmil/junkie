# VR-телеоперация и сбор демонстраций: обзор для команды

## Scope

Десять готовых или полуготовых стеков для Quest 3, одноруких манипуляторов и сбора данных. Приоритет: AgileX Piper/Piper X, LeRobot, Isaac Sim/Lab. Оценка доработки — для работающего исследовательского стенда, не для промышленной эксплуатации.

**Обозначения визуализации:** V0 — Quest только задаёт команды; V1 — passthrough с интерфейсом; V2 — видеопанель камер робота/сима; V3 — стереоизображение камер или виртуальной сцены на всё поле зрения.

**Ключевое различие:** Quest-ввод, обратное видео и датасет — три независимых канала. Камеры Quest/passthrough обычно не пишутся в датасет. Для policy записываются камеры робота либо камеры симулятора.

## Краткий выбор

- **Быстрый старт с обычным Piper + LeRobot:** `piper-robot-server`.
- **Готовый пример управления Piper из Quest:** Neuracore `example_agilex`; потребуется отдельный экспорт в LeRobot.
- **Своя открытая интеграция с хорошим интерфейсом и видео:** `vr-teleop-kit` + Piper backend.
- **Sim-first, полноценная VR-сцена и генерация данных:** Isaac Lab + Isaac Teleop.
- **Piper X:** не подменять им обычный Piper без отдельной проверки URDF/USD, порядка суставов, лимитов, знаков осей и драйвера.

## Сравнение

| № | Проект | Ввод и управление | Визуализация | Симулятор | Запись | Piper / объём интеграции |
|---:|---|---|---|---|---|---|
| 1 | [`piper-robot-server`](https://github.com/TactileRoboticsAI/piper-robot-server) | Quest/WebXR, контроллеры, IK | V0; камерный канал есть, но слабо описан | режим без робота; Isaac/MuJoCo через адаптер | LeRobot: action, state, cameras | Piper 1–2/5; Piper X 3/5 |
| 2 | [`example_agilex`](https://github.com/NeuracoreAI/example_agilex) | контроллер Quest, dead-man, IK | V0/V1 | собственного сима нет | формат Neuracore, replay | Piper 1/5; Piper X 2–3/5 |
| 3 | [`vr-teleop-kit`](https://github.com/Dream-Machines-Robotics/vr-teleop-kit) | controllers, clutch, precision mode | V1/V2, WebRTC | MuJoCo готов; Isaac через backend | LeRobot | Piper/Piper X 3/5 |
| 4 | [`TeleopXR`](https://github.com/qrafty-ai/teleop_xr) | controllers/hands, relative pose | V1/V2, WebRTC, 3D-модель | Python/ROS2; Isaac/MuJoCo через backend | рекордер подключается отдельно | Piper + LeRobot 3/5 |
| 5 | [`OpenTeach`](https://github.com/aadhithya14/Open-Teach) | hand tracking и перенос движений руки | V1/V2 | Isaac Gym, LIBERO; Isaac Sim через адаптер | AVI + HDF5 | Piper 4/5 |
| 6 | [`Quest2ROS2`](https://github.com/Taokt/Quest2ROS2) | controllers, relative pose, clutch | V0; RViz на ПК | любой ROS2 sim, включая Isaac Sim | rosbag2/MCAP добавляются отдельно | Piper с ROS2 3/5 |
| 7 | [`XRoboToolkit`](https://github.com/StackX-Official/XRoboToolkit) | controllers, hands, head, trackers | V0 в sample | MuJoCo; Isaac через адаптер | PKL, есть пример конверсии | Piper 3/5 |
| 8 | [`Open-TeleVision`](https://github.com/OpenTeleVision/TeleVision) | hand/head tracking, retargeting | V3, стереокамеры | Isaac Gym demo | SVO/HDF5 | Piper 4/5 |
| 9 | [`Isaac Teleop`](https://github.com/NVIDIA/IsaacTeleop) / Isaac ROS | controllers, hands, иногда body input | V2/V3, CloudXR | Isaac Sim/Lab, ROS2 | MCAP + выбранный рекордер | Piper 3–4/5 |
| 10 | [`Isaac Lab`](https://github.com/isaac-sim/IsaacLab) | Quest/PICO, Cartesian или joint control | V3 | Isaac Sim | HDF5, replay, annotation | Piper 3–4/5 |

---

# 1. `piper-robot-server`

**Архитектура.** WebXR-клиент на Quest передаёт позы контроллеров на рабочую машину. Там Pinocchio/CasADi решает IK по модели Piper, а control loop отправляет суставные команды через Piper stack/CAN.

**Управление и изображение.** Контроллеры Quest; детали button map стоит проверить в версии клиента. Базовый режим — V0. Есть mono/stereo camera modes и отправка через Tactile SDK, но законченный Quest-video workflow публично не описан.

**Симулятор.** `robotserver --no-robot --vis` годится для проверки mapping/IK, но это не физический симулятор. Для Isaac Sim или MuJoCo заменяется только backend: вместо CAN принимается тот же EE/joint target, а backend отдаёт state и virtual cameras.

**Данные и workflow.** Сначала `--no-robot --vis`, затем `robotserver --record --repo-id …`; оператор запускает/сохраняет/отбрасывает эпизод клавишами на рабочей машине. Записываются `action`, `observation.state`, `observation.images.<camera>`; по умолчанию 30 FPS, видео может быть собрано после сессии.

**Для Piper.** Наиболее короткий путь к LeRobot. Для Piper X отдельно валидировать геометрию, лимиты и драйвер. Полезные расширения: wrist camera, depth, force/gripper state, метка success.

---

# 2. Neuracore `example_agilex` + `meta_quest_teleop`

**Архитектура.** Специализированный пример Piper + Quest + RealSense. Рабочая машина принимает контроллер, рассчитывает движение Piper и отправляет команды по CAN; Neuracore хранит траектории, поддерживает replay и rollout модели.

**Управление и изображение.** Правый контроллер; `Right Grip` — dead-man/clutch, `Right Trigger` — схват, `A` — enable, `B` — home. В Quest нет готового экрана камеры: V0/V1, оператор пользуется passthrough или монитором.

**Симулятор.** Прямого backend нет. Для Isaac Sim заменить класс real-robot control на класс, работающий с articulation; вход, mapping и логика сессии сохраняются.

**Данные и workflow.** Настроить CAN/RealSense, проверить скорость и сглаживание, включить робота, удерживать `Right Grip`, выполнить демонстрацию, закрыть эпизод средствами Neuracore. Формат ориентирован на Neuracore, поэтому для LeRobot нужен конвертер либо замена recorder layer.

**Для Piper.** Самый готовый вариант на физическом Piper. Для Piper X — отдельный драйвер и проверка модели. Логично добавить LeRobot recorder и видео в Quest через WebRTC.

---

# 3. Dream Machines `vr-teleop-kit`

**Архитектура.** WebXR relay принимает контроллеры Quest; robot-specific часть преобразует pose в команду руки. В поставке есть реализация для TRLC-DK1 и MuJoCo, а запись опирается на LeRobot.

**Управление и изображение.** Relative clutch, precision mode и haptics. Quest может работать в passthrough, а камеры выводятся WebRTC-панелями в сцене (V1/V2).

**Симулятор.** MuJoCo — штатный вариант. Для Isaac Sim нужен Piper controller/backend, который принимает тот же target и публикует observation; relay и интерфейс Quest менять не требуется.

**Данные и workflow.** Поднять relay и камеры, калибровать рабочую зону, подключить `lerobot-record`, записать и принять/отбросить эпизод средствами LeRobot. Итоговый формат — LeRobotDataset.

**Для Piper.** Нужны Piper URDF, IK/Cartesian controller и adapter к Piper driver. Это хороший вариант, если важны видеопанели и управляемый UX, а не готовый Piper stack.

---

# 4. Qrafty AI TeleopXR

**Архитектура.** Универсальный XR-фронтенд с отдельными transport, robot model и control слоями. В готовых примерах есть Franka, SO-101 и OpenArm; Piper подключается как ещё один robot plugin.

**Управление и изображение.** Quest controllers или hand tracking, relative pose с удержанием grip, 3D-визуализация и WebRTC video (V1/V2).

**Симулятор.** Python/ROS2 являются естественными точками подключения. Для Isaac Sim или MuJoCo реализуется backend с `send_action`, `get_observation` и camera stream.

**Данные и workflow.** Поднять relay/server, модель робота и камеры; проверить control mapping; включить внешний recorder (LeRobot или rosbag2); завершать эпизоды UI-кнопкой или отдельным сервисом task success.

**Для Piper.** Потребуются модель, IK и драйвер; рекордер не встроен. Удобен для системы, где визуализация и управление должны быть независимы от конкретной руки.

---

# 5. OpenTeach

**Архитектура.** Стек для hand/arm teleoperation и сбора демонстраций, прежде всего для многопалых рук. Поддерживает несколько манипуляторов и перенос движения человеческой кисти на робот.

**Управление и изображение.** Hand tracking Quest 3, retargeting кисти; passthrough и отдельный camera screen (V1/V2). Для однозахватного Piper большая часть hand-retargeting избыточна: достаточно EE pose + gripper command.

**Симулятор.** В проекте есть Isaac Gym и LIBERO. Isaac Sim требует отдельного Piper controller и возврата state/cameras в его interface.

**Данные и workflow.** Запустить Quest app, robot/camera servers, проверить mapping, затем `data_collect.py`; после сессии отфильтровать неудачные траектории. Выход: AVI для камер, HDF5 для state/depth/sensors.

**Для Piper.** Нужен adapter и конвертер HDF5 → LeRobot, плюс нормальная логика accept/reject эпизода. Оправдан, если ожидается переход к кистям, bimanual или tactile data.

---

# 6. Quest2ROS2

**Архитектура.** Quest публикует controllers/buttons в ROS2; далее обычные ROS2 nodes выполняют mapping, IK, safety и управление роботом. Это транспорт и ввод, а не готовый data-collection stack.

**Управление и изображение.** Relative motion и re-anchor target при отпускании кнопки; отдельная кнопка для схвата. Базово V0; RViz используется на рабочей машине. Видео в Quest добавляется отдельным WebRTC/OpenXR приложением.

**Симулятор.** Isaac Sim хорошо подходит через ROS2 bridge; MuJoCo также возможен через ROS2 controller. Переключение real/sim делается заменой ROS2 backend, а не Quest-приложения.

**Данные и workflow.** Запустить robot/sim driver, ROS2 nodes и RViz, задать home/reference, выполнить телепоказ. Запись — `rosbag2`/MCAP; затем синхронизировать state, action и camera timestamps и конвертировать в LeRobot.

**Для Piper.** Рационален, если ROS2 уже является основой стенда. Добавить Cartesian controller, safety limits, rosbag schema и LeRobot exporter.

---

# 7. XRoboToolkit Teleop Sample Python

**Архитектура.** XRoboToolkit нормализует ввод с controllers/hands/head/trackers; sample соединяет его с MuJoCo и записывает XR input, state, actions и камеры.

**Управление и изображение.** Grip разрешает движение, trigger управляет схватом; в sample V0. Видеоканал можно добавить поверх transport, не меняя control loop.

**Симулятор.** MuJoCo есть в примере. Для Isaac Sim повторяется тот же controller contract: XR input → target → Piper articulation → observation.

**Данные и workflow.** Настроить hardware profile и MuJoCo scene, проверить mapping, собрать эпизоды, прогнать встроенную проверку. Выход — `.pkl`; в проекте есть пример конверсии в LeRobot для двухрукой системы.

**Для Piper.** Нужны Piper model/driver и adapter формата данных. Уместен, если возможны дополнительные трекеры или разные VR-устройства.

---

# 8. Open-TeleVision

**Архитектура.** Система с упором на stereo telepresence: head pose и руки оператора управляют роботом, а оператор получает активное стереоизображение с камер. Исходно рассчитана на dexterous/bimanual setups.

**Управление и изображение.** Hand tracking, head pose и retargeting; V3 через ZED stereo cameras. Quest 3 подключается через WebXR; для удалённого доступа потребуется сетевой слой, например VPN/TURN.

**Симулятор.** Есть Isaac Gym demo. Для Isaac Sim переносится control + camera path на виртуальную модель; изображение можно отдать через штатную web-страницу или CloudXR.

**Данные и workflow.** Калибровать стереокамеры и coordinate frames, проверить задержку, выполнить демонстрацию, завершить/отбросить эпизод на recorder side. Данные: ZED SVO плюс обработанный HDF5; в проекте есть pipeline ACT.

**Для Piper.** Для одной простой руки это тяжёлая система; интеграция оправдана, когда критичны естественный бинокулярный обзор, head tracking и последующий переход к двум рукам.

---

# 9. NVIDIA Isaac Teleop / Isaac ROS Teleop

**Архитектура.** NVIDIA-стек объединяет Quest/PICO input, Isaac Sim/Lab и ROS2 robots. Графы преобразуют XR pose в команды модели/робота; CloudXR передаёт изображение виртуальной сцены в шлем.

**Управление и изображение.** Controllers, hands и в части сценариев body input. Камеры, model view и виртуальная сцена доступны как V2/V3. Весь тяжёлый runtime находится на рабочей станции с NVIDIA GPU.

**Симулятор.** Isaac Sim/Lab и ROS2 — штатные варианты. Для real Piper нужен ROS2/driver adapter; для виртуального Piper — URDF/USD, controller и task config.

**Данные и workflow.** Запустить Isaac/CloudXR и teleop graph, выполнить calibration, проверить сцены без записи, затем включить MCAP для device stream и выбранный recorder для robot state/cameras. Dataset layer выбирается отдельно: rosbag2, Isaac Lab HDF5 или LeRobot.

**Для Piper.** Хорошая база для общего real/sim pipeline, но не готовое решение для Piper. Сначала требуется надёжная модель и управляющий слой Piper.

---

# 10. Isaac Lab

**Архитектура.** Isaac Lab поверх Isaac Sim предназначен для task definition, teleop demonstrations, replay, annotation и синтетического расширения данных. XR-ввод обычно приходит через Isaac Teleop/CloudXR.

**Управление и изображение.** Hand tracking Quest/PICO задаёт Cartesian или joint targets. Оператор находится в виртуальной сцене (V3); camera/raster rendering выполняется на GPU рабочей машины.

**Симулятор.** Это штатная среда Isaac Sim. Для Piper необходимы корректный USD/URDF, articulation drives, gripper, камеры, reset distribution и success predicate. С реальным Piper важно унифицировать joint order, units, gripper normalization и rate.

**Данные и workflow.** Сначала запустить Piper task без записи и воспроизвести action; затем `record_demos.py --xr`, принимать только успешные эпизоды, проверять их replay, размечать `annotate_demos.py`, при необходимости расширять `generate_dataset.py`. Выход — HDF5; перед смешиванием с реальными данными нужен exporter в LeRobot.

**Для Piper.** Лучший вариант для большого sim dataset, вариативных сцен, RGB/depth/segmentation и проверки policy до железа. Цена — начальная работа над asset и task.

---

## Общий контракт real/sim

Для всех проектов разумно держать один interface между teleop и backend:

```text
XR frame (poses, buttons, hand joints)
  → mapping / clutch / limits
  → RobotCommand (EE target или joint target, gripper, timestamp)
  → Piper CAN backend | Isaac backend | MuJoCo backend
  → RobotObservation (state, cameras, timestamp)
  → video to Quest + episode recorder
```

Минимум backend API: `reset`, `send_action`, `get_observation`, `is_success`, `close`. В датасет писать применённое action после safety clipping, а не raw pose контроллера.

## Рекомендация для Piper + Quest 3 + LeRobot

1. Начать с `piper-robot-server`, двух камер (front + wrist) и LeRobotDataset; сначала убедиться, что state/action/cameras синхронизированы и replay дают ожидаемую траекторию.
2. Если нужен video-first интерфейс в Quest, взять `vr-teleop-kit` как XR/UI слой и заменить его robot backend на Piper.
3. Если нужен sim-first процесс, собрать Piper task в Isaac Lab и писать HDF5/LeRobot по той же схеме полей, что на реальном роботе.
4. Перед сбором массового датасета зафиксировать names/order суставов, frame conventions, частоту, gripper encoding, camera calibration, task schema и критерий success. Это важнее выбора конкретного XR-фронтенда.
