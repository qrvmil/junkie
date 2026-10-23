# ROS 2 Jazzy: справка по методам Python

Здесь описаны методы `rclpy`, которые понадобятся для [задания](task.md), и приведены ссылки на документацию. Требования к нодам и поля сообщений указаны в условии.

## Нода, publisher, subscription и timer

Класс `rclpy.node.Node` предоставляет методы создания участников ROS. Сохраните созданные объекты в своей ноде, чтобы обращаться к ним во время работы.

| API | Что передать и что происходит |
|---|---|
| `Node.create_publisher` | Тип сообщения, имя топика и QoS. Возвращает publisher |
| `Publisher.publish` | Заполненный объект сообщения; отправляет его подписчикам |
| `Node.create_subscription` | Тип сообщения, имя топика, callback и QoS. Callback получает сообщение |
| `Node.create_timer` | Период в секундах и callback. Executor вызывает callback при срабатывании таймера |
| `Node.get_logger` | Возвращает logger; его метод `info` выводит сообщение ноды |

Для собственных интерфейсов смотрите классы `RobotCommand` и `RobotState` в `courier_interfaces.msg`. Поля объекта сообщения называются так же, как в `.msg`.

Аргумент QoS `10` задаёт глубину истории 10 с политикой keep last; стандартные reliability и durability для этого профиля — reliable и volatile. Примените одинаковые настройки к publisher и subscription обоих топиков. Volatile не выдаёт позднему подписчику сообщения, опубликованные до его подключения.

В функции `main` нужны `rclpy.init`, создание ноды и работа executor. `rclpy.spin` обрабатывает события ноды. При завершении используйте `Node.destroy_node` и `rclpy.shutdown`.

Документация Jazzy: [publisher и subscriber](https://docs.ros.org/en/jazzy/Tutorials/Beginner-Client-Libraries/Writing-A-Simple-Py-Publisher-And-Subscriber.html), [API Node](https://docs.ros.org/en/jazzy/p/rclpy/rclpy.node.html), [QoS](https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html).

## Сервис: короткий запрос и ответ

`GetRoute` находится в `courier_interfaces.srv`. У него есть типы `GetRoute.Request` и `GetRoute.Response`.

Сервер создаётся методом `Node.create_service`: нужны тип сервиса, имя и callback. Callback получает запрос и объект ответа, заполняет ответ и возвращает его. Время выполнения обработчика должно быть коротким.

Клиент создаётся методом `Node.create_client`. `Client.service_is_ready` позволяет проверить доступность сервиса; `Client.wait_for_service` ждёт его появления. Для запроса используйте `Client.call_async`: он возвращает `rclpy.task.Future`, который завершится при получении ответа. Метод `Future.add_done_callback` регистрирует обработчик завершения; готовый ответ извлекается через `Future.result`. Пока ответ не получен, executor должен продолжать работать.

Перед `call_async` дождитесь доступности сервиса именно через свой клиент. Сам `call_async` не ждёт появления сервера. Если проверка выполняется из callback, можно повторять `service_is_ready` коротким обработчиком таймера и отправить запрос, когда сервис станет доступен.

Не вызывайте блокирующий `Client.call` из callback. В этом задании диспетчер должен принимать отмену даже при задержке ответа каталога. Регистрация обработчика завершения запроса позволяет продолжить обработку других событий.

Документация Jazzy: [сервис и клиент на Python](https://docs.ros.org/en/jazzy/Tutorials/Beginner-Client-Libraries/Writing-A-Simple-Py-Service-And-Client.html), [API Client](https://docs.ros.org/en/jazzy/p/rclpy/rclpy.client.html).

## Action-сервер: приём, feedback, результат и отмена

Используйте класс `rclpy.action.ActionServer` и тип `ExecuteRoute` из `courier_interfaces.action`. Конструктору нужны нода, тип, имя action и `execute_callback`. Дополнительные аргументы `goal_callback` и `cancel_callback` задают обработчики приёма цели и запроса отмены.

| API | Назначение |
|---|---|
| `goal_callback` | Получает `ExecuteRoute.Goal`; возвращает `GoalResponse.ACCEPT` или `GoalResponse.REJECT` |
| `handle_accepted_callback` | Необязательный обработчик принятой цели; получает `ServerGoalHandle` до запуска исполнения |
| `execute_callback` | Получает `ServerGoalHandle` принятой цели; должен вернуть заполненный `ExecuteRoute.Result` |
| `ServerGoalHandle.request` | Исходный goal |
| `ServerGoalHandle.publish_feedback` | Отправляет заполненный `ExecuteRoute.Feedback` |
| `ServerGoalHandle.succeed` | Устанавливает статус успешного завершения |
| `ServerGoalHandle.abort` | Устанавливает статус неудачного завершения |
| `cancel_callback` | Получает goal handle; возвращает `CancelResponse.ACCEPT` или `CancelResponse.REJECT` |
| `ServerGoalHandle.is_cancel_requested` | Показывает, что цель переведена в состояние отмены |
| `ServerGoalHandle.canceled` | Устанавливает окончательный статус отменённой цели |

Статус завершения и поля result — разные части ответа. Установить статус недостаточно: `execute_callback` должен вернуть result. Принять запрос отмены также недостаточно: это только согласие начать отмену. Условие задания определяет, какое подтверждение нужно получить до окончательного `CANCELED`. `cancel_callback` должен быстро вернуть решение: переход цели в состояние отмены происходит после его возврата. Не ожидайте остановку и не вызывайте `canceled` прямо в этом обработчике.

По умолчанию `ActionServer` принимает все цели и отклоняет запросы отмены. Напишите свои обработчики. Отказ пустому goal и второй цели не появится автоматически. Занятость должна учитываться уже при приёме цели, а не только при начале её исполнения.

До начала обработки отмены данные принятой цели должны быть готовы. Для их подготовки можно использовать `handle_accepted_callback`. Если вы переопределили этот обработчик, вызов `ServerGoalHandle.execute` для запуска исполнения становится вашей обязанностью; стандартный обработчик вызывает его сам.

Документация Jazzy: [action-сервер и клиент](https://docs.ros.org/en/jazzy/Tutorials/Intermediate/Writing-an-Action-Server-Client/Py.html), [API ActionServer и ServerGoalHandle](https://docs.ros.org/en/jazzy/p/rclpy/rclpy.action.server.html).

## Ожидание события без блокировки ноды

Executor вызывает обработчики сообщений, таймеров, сервиса и action. Если обработчик занимает его циклом ожидания или `time.sleep`, сообщения, от которых зависит завершение ожидания, могут остаться необработанными. Несколько потоков сами по себе не устраняют блокировку callback group.

Для этого задания подходит `SingleThreadedExecutor` и асинхронный `execute_callback`, который ждёт завершения `rclpy.task.Future`. Объект Future хранит результат, который появится позже.

При выполнении callbacks работающий executor доступен через `Node.executor`; его метод `create_future` создаёт Future, связанную с этим executor. `rclpy.spin` по умолчанию использует однопоточный executor.

Когда нужное событие действительно произошло, ваш короткий обработчик завершает Future методом `set_result`. Метод `done` позволяет проверить, что она ещё не завершена. Объект ожидания нужно создать до события, которое его завершает, и хранить отдельно для каждой принятой цели. Сервисный запрос имеет собственную Future и собственный обработчик ответа.

Объявление `async def` делает функцию корутиной. Внутри неё `await` незавершённой `rclpy.task.Future` приостанавливает эту корутину и даёт executor обрабатывать другие события. После завершения Future корутина продолжает работу и может вернуть результат. Не ждите в `execute_callback` только ответа каталога, если это задержит окончательное завершение отмены до получения этого ответа.

Используйте именно Future из `rclpy`, а не `asyncio.Future`: обычный ROS executor не запускает цикл событий `asyncio`. Для описанного способа собственные потоки и цикл `asyncio` не нужны. Наличие `async def` без подходящего `await` не освобождает executor.

При создании `ActionServer` передайте в `callback_group` экземпляр `rclpy.callback_groups.ReentrantCallbackGroup` и сохраните его в ноде. Action включает несколько служебных callbacks: запрос результата тоже может ждать завершения цели. Reentrant group позволяет обрабатывать goal, cancel и другие события action во время такого ожидания.

Группа по умолчанию — `MutuallyExclusiveCallbackGroup`, которая допускает только один свой callback за раз. Даже при `await` она может задержать нужное событие. Подписку на состояние и клиента каталога можно оставить в отдельной группе ноды по умолчанию; их callbacks должны быть короткими.

Документация Jazzy: [callback groups и взаимные блокировки](https://docs.ros.org/en/jazzy/How-To-Guides/Using-callback-groups.html), [Future](https://docs.ros.org/en/jazzy/p/rclpy/rclpy.task.html), [executor](https://docs.ros.org/en/jazzy/p/rclpy/rclpy.executors.html). Исходники `rclpy` для Jazzy: [Future и Task](https://github.com/ros2/rclpy/blob/jazzy/rclpy/rclpy/task.py), [executor](https://github.com/ros2/rclpy/blob/jazzy/rclpy/rclpy/executors.py), [ActionServer](https://github.com/ros2/rclpy/blob/jazzy/rclpy/rclpy/action/server.py).

## Action-клиент: четыре разных ответа

`rclpy.action.ActionClient` создаётся с нодой, типом `ExecuteRoute` и именем action. Проверить наличие сервера можно через `server_is_ready`; дождаться его — через `wait_for_server`. Если ждать из callback, не блокируйте executor: проверяйте готовность коротким обработчиком таймера. Ожидание до начала `spin` допустимо, пока ноде ещё не нужны другие callbacks.

| API | Что получает оператор |
|---|---|
| `ActionClient.send_goal_async` | Future ответа о приёме goal; аргумент `feedback_callback` задаёт обработчик feedback |
| `ClientGoalHandle.accepted` | Принял ли сервер цель |
| Feedback callback | Сообщение-обёртку: поля вашего feedback находятся в его поле `feedback` |
| `ClientGoalHandle.get_result_async` | Future окончательного ответа с полями `status` и `result` |
| `ClientGoalHandle.cancel_goal_async` | Future ответа на запрос отмены |

Обработчики завершения регистрируются через `add_done_callback`; готовый ответ читается через `result`. Для расшифровки окончательного `status` используйте константы `action_msgs.msg.GoalStatus`, например `STATUS_SUCCEEDED`, `STATUS_CANCELED` и `STATUS_ABORTED`. После согласия на отмену продолжайте ждать окончательный result.

Документация Jazzy: [API ActionClient и ClientGoalHandle](https://docs.ros.org/en/jazzy/p/rclpy/rclpy.action.client.html).

## Параметры и файл маршрутов

`Node.declare_parameter` объявляет параметр с его значением по умолчанию. `Node.get_parameter` возвращает параметр, а его свойство `value` — значение. В этой работе нужны строковые `routes_file` у каталога и `route_name` у оператора, а также целочисленный `cancel_after_feedback` у оператора. Значения по умолчанию указаны в условии.

CLI позволяет переопределить параметр при запуске:

```bash
ros2 run courier_nodes route_server --ros-args -p routes_file:=/work/courier_ws/config/routes.yaml
ros2 run courier_nodes operator --ros-args -p route_name:=full -p cancel_after_feedback:=5
```

Документация Jazzy: [параметры Python-ноды](https://docs.ros.org/en/jazzy/Tutorials/Beginner-Client-Libraries/Using-Parameters-In-A-Class-Python.html).

`config/routes.yaml` содержит обычные данные, а не ROS-файл параметров:

```yaml
routes:
  short: [room_a, warehouse]
  full: [room_a, room_b, warehouse]
```

Каталог читает путь из `routes_file`. Значение по умолчанию — `config/routes.yaml`; относительный путь отсчитывается от текущего рабочего каталога процесса. При запуске из `/work/courier_ws` он указывает на выданный файл.

Откройте файл для чтения и передайте его в `yaml.safe_load` из PyYAML. Полученный документ — словарь Python; его раздел `routes` доступен как `document['routes']`. Внутри находятся названия маршрутов и списки строк. Читайте эти данные из файла, чтобы каталог учитывал путь, переданный параметром. PyYAML уже установлен в выданном контейнере; зависимость `python3-yaml` указывается в `package.xml` вашего пакета.

Справка библиотеки: [PyYAML: safe_load](https://pyyaml.org/wiki/PyYAMLDocumentation).

## Посмотреть интерфейсы и соединения

Команды выполняются внутри контейнера после подключения Jazzy и собранного workspace. Они помогают проверить типы и наличие участников ROS:

```bash
ros2 interface show courier_interfaces/msg/RobotState
ros2 interface show courier_interfaces/srv/GetRoute
ros2 interface show courier_interfaces/action/ExecuteRoute
ros2 node list
ros2 topic info /courier/state --verbose
ros2 service list -t
ros2 action info /courier/execute_route
```

Команды для отправки сообщений, запроса маршрута и goal приведены в [условии](task.md). Начинайте проверку с отдельных нод, затем запускайте систему целиком.
