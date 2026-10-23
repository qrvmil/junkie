# Развертывание YARN

## Цель

Развернуть **YARN** поверх уже работающего HDFS-кластера и обеспечить доступ к веб-интерфейсам основных и вспомогательных демонов.

После выполнения роли будут распределены следующим образом:


| Узел         | HDFS                        | YARN / MapReduce                  |
| ------------ | --------------------------- | --------------------------------- |
| `edge.example.invalid` | DataNode, SecondaryNameNode | NodeManager                       |
| `nn.example.invalid` | NameNode                    | ResourceManager, JobHistoryServer |
| `dn01.example.invalid` | DataNode                    | NodeManager                       |
| `dn02.example.invalid` | DataNode                    | NodeManager                       |


Итоговая схема:

```text
nn.example.invalid
├── NameNode
├── ResourceManager
└── JobHistoryServer

edge.example.invalid
├── DataNode
├── SecondaryNameNode
└── NodeManager

dn01.example.invalid
├── DataNode
└── NodeManager

dn02.example.invalid
├── DataNode
└── NodeManager
```

---



## Шаг 1. Проверить существующий HDFS-кластер

Подключиться с локального компьютера к edge-ноде:

```bash
ssh cluster-admin@203.0.113.10
```

Переключиться на пользователя `hadoop`:

```bash
sudo -iu hadoop
source ~/.bashrc
```

Проверить состояние HDFS:

```bash
hdfs dfsadmin -report
```

В выводе должно быть:

```text
Live datanodes (3)
```

---



## Шаг 2. Настроить MapReduce для работы через YARN

Конфигурационные файлы сначала редактируем на `edge.example.invalid`, после чего распространяем на остальные узлы.

На edge-ноде под пользователем `hadoop`:

```bash
cd ~/hadoop-3.4.0/etc/hadoop
```

Открыть:

```bash
nano mapred-site.xml
```

Добавить конфигурацию:

```xml
<?xml version="1.0"?>
<configuration>

    <property>
        <name>mapreduce.framework.name</name>
        <value>yarn</value>
    </property>

    <property>
        <name>mapreduce.application.classpath</name>
        <value>$HADOOP_MAPRED_HOME/share/hadoop/mapreduce/*:$HADOOP_MAPRED_HOME/share/hadoop/mapreduce/lib/*</value>
    </property>

    <property>
        <name>mapreduce.jobhistory.address</name>
        <value>nn.example.invalid:10020</value>
    </property>

    <property>
        <name>mapreduce.jobhistory.webapp.address</name>
        <value>nn.example.invalid:19888</value>
    </property>

</configuration>
```

Здесь:

- `mapreduce.framework.name` переводит MapReduce на выполнение через YARN;
- `mapreduce.application.classpath` задает необходимые библиотеки MapReduce;
- `mapreduce.jobhistory.address` задает адрес JobHistoryServer;
- порт `19888` используется для его веб-интерфейса.

---



## Шаг 3. Настроить YARN

На `edge.example.invalid` перейти в каталог конфигурации Hadoop:

```bash
cd ~/hadoop-3.4.0/etc/hadoop
```

Открыть:

```bash
nano yarn-site.xml
```

Добавить:

```xml
<?xml version="1.0"?>
<configuration>

    <property>
        <name>yarn.resourcemanager.hostname</name>
        <value>nn.example.invalid</value>
    </property>

    <property>
        <name>yarn.resourcemanager.webapp.address</name>
        <value>nn.example.invalid:8088</value>
    </property>

    <property>
        <name>yarn.nodemanager.aux-services</name>
        <value>mapreduce_shuffle</value>
    </property>

    <property>
        <name>yarn.nodemanager.env-whitelist</name>
        <value>JAVA_HOME,HADOOP_COMMON_HOME,HADOOP_HDFS_HOME,HADOOP_CONF_DIR,CLASSPATH_PREPEND_DISTCACHE,HADOOP_YARN_HOME,HADOOP_HOME,PATH,LANG,TZ,HADOOP_MAPRED_HOME</value>
    </property>

</configuration>
```

В этой конфигурации:

- `nn.example.invalid` назначается ResourceManager;
- `8088` — порт веб-интерфейса ResourceManager;
- `mapreduce_shuffle` позволяет выполнять MapReduce через NodeManager.

---



## Шаг 4. Проверить список worker-нод

Открыть файл:

```bash
nano ~/hadoop-3.4.0/etc/hadoop/workers
```

В нем должны находиться три worker-ноды:

```text
edge.example.invalid
dn01.example.invalid
dn02.example.invalid
```

На этих трех узлах YARN должен запустить `NodeManager`.

`nn.example.invalid` в список не добавляется, так как на нем будет работать `ResourceManager`.

---



## Шаг 5. Распространить конфигурацию по кластеру

На занятии конфигурационные файлы сначала редактировались на edge-ноде, после чего копировались на остальные машины. Используем такую же схему.

На `edge.example.invalid` под пользователем `hadoop`:

```bash
cd ~/hadoop-3.4.0/etc/hadoop
```

Скопировать конфигурацию на NameNode:

```bash
scp mapred-site.xml yarn-site.xml workers \
hadoop@nn.example.invalid:/home/hadoop/hadoop-3.4.0/etc/hadoop/
```

Скопировать на первый DataNode:

```bash
scp mapred-site.xml yarn-site.xml \
hadoop@dn01.example.invalid:/home/hadoop/hadoop-3.4.0/etc/hadoop/
```

Скопировать на второй DataNode:

```bash
scp mapred-site.xml yarn-site.xml \
hadoop@dn02.example.invalid:/home/hadoop/hadoop-3.4.0/etc/hadoop/
```

Теперь все узлы используют одинаковую конфигурацию YARN и MapReduce.

> **Замечание:** если узлы не разрешаются по именам (`nn.example.invalid`, `dn01.example.invalid`, `dn02.example.invalid`), необходимо проверить `/etc/hosts`. На занятии именно неправильное разрешение имен стало причиной того, что NodeManager не мог подключиться к ResourceManager.

---



## Шаг 6. Запустить YARN

С edge-ноды перейти на NameNode:

```bash
ssh hadoop@nn.example.invalid
```

Загрузить переменные окружения:

```bash
source ~/.bashrc
```

Перейти в Hadoop:

```bash
cd ~/hadoop-3.4.0
```

Запустить YARN:

```bash
sbin/start-yarn.sh
```

Команда должна:

- запустить `ResourceManager` на `nn.example.invalid`;
- запустить `NodeManager` на `edge.example.invalid`;
- запустить `NodeManager` на `dn01.example.invalid`;
- запустить `NodeManager` на `dn02.example.invalid`.

---



## Шаг 7. Запустить JobHistoryServer

На `nn.example.invalid`:

```bash
mapred --daemon start historyserver
```

Проверить процессы:

```bash
jps
```

На `nn.example.invalid` должны присутствовать как минимум:

```text
NameNode
ResourceManager
JobHistoryServer
```

`NameNode` относится к уже работающему HDFS, а `ResourceManager` и `JobHistoryServer` добавляются в ДЗ №2.

---



## Шаг 8. Проверить три NodeManager

Проверить состояние YARN:

```bash
yarn node -list -all
```

В списке должны находиться три NodeManager со статусом `RUNNING`:

```text
edge.example.invalid
dn01.example.invalid
dn02.example.invalid
```

При необходимости можно дополнительно проверить процессы непосредственно на worker-нодах:

```bash
ssh hadoop@edge.example.invalid jps
ssh hadoop@dn01.example.invalid jps
ssh hadoop@dn02.example.invalid jps
```

На каждой должен присутствовать:

```text
NodeManager
```

---



## Шаг 9. Проверить выполнение задания через YARN

Создать небольшой тестовый файл:

```bash
printf 'one two two three three three\n' > ~/yarn-test.txt
```

Создать каталог в HDFS:

```bash
hdfs dfs -mkdir -p /user/hadoop/yarn-input
```

Загрузить файл:

```bash
hdfs dfs -put -f ~/yarn-test.txt /user/hadoop/yarn-input/input.txt
```

Удалить старый тестовый результат, если он существует:

```bash
hdfs dfs -rm -r -f /user/hadoop/yarn-output
```

Запустить стандартный пример `WordCount`:

```bash
hadoop jar \
$HADOOP_HOME/share/hadoop/mapreduce/hadoop-mapreduce-examples-3.4.0.jar \
wordcount \
/user/hadoop/yarn-input \
/user/hadoop/yarn-output
```

Посмотреть результат:

```bash
hdfs dfs -cat /user/hadoop/yarn-output/part-r-00000
```

Ожидаемый результат:

```text
one     1
three   3
two     2
```

Успешное выполнение подтверждает, что MapReduce-задача была передана YARN, выполнена на worker-нодах и результат записан обратно в HDFS.

---



## Шаг 10. Опубликовать веб-интерфейсы

Для проверки используются следующие интерфейсы:


| Сервис           | Узел         | Порт    |
| ---------------- | ------------ | ------- |
| ResourceManager  | `nn.example.invalid` | `8088`  |
| JobHistoryServer | `nn.example.invalid` | `19888` |
| NodeManager      | `edge.example.invalid` | `8042`  |
| NodeManager      | `dn01.example.invalid` | `8042`  |
| NodeManager      | `dn02.example.invalid` | `8042`  |


Внутренние VM напрямую из интернета недоступны, поэтому для проверки с локального компьютера можно использовать SSH-туннель через edge-ноду.

Команду выполнять **на локальном компьютере**:

```bash
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 -N \
-L 8088:192.0.2.11:8088 \
-L 19888:192.0.2.11:19888 \
-L 18042:192.0.2.10:8042 \
-L 18043:192.0.2.12:8042 \
-L 18044:192.0.2.13:8042 \
cluster-admin@203.0.113.10
```

Пока SSH-соединение открыто, интерфейсы доступны в браузере:

```text
ResourceManager:
http://localhost:8088

JobHistoryServer:
http://localhost:19888

NodeManager edge.example.invalid:
http://localhost:18042

NodeManager dn01.example.invalid:
http://localhost:18043

NodeManager dn02.example.invalid:
http://localhost:18044
```

> **Замечание:** SSH-туннель предоставляет внешний доступ через edge для локальной проверки. Если в рамках курса под «опубликовать» требуется именно публичный URL, доступный без SSH, необходимо отдельно настроить публикацию через edge-ноду (например, reverse proxy) в соответствии с требованиями преподавателя.

---



## Шаг 11. Финальная проверка

Открыть веб-интерфейс ResourceManager:

```text
http://localhost:8088
```

В нем должны отображаться **3 активных NodeManager**.

Проверить JobHistoryServer:

```text
http://localhost:19888
```

После выполнения `WordCount` в нем должна отображаться завершенная MapReduce-задача.

Также проверить:

```bash
yarn node -list -all
```

Должно быть три работающих NodeManager.

На `nn.example.invalid`:

```bash
jps
```

Ожидаются:

```text
NameNode
ResourceManager
JobHistoryServer
```

На `edge.example.invalid`:

```text
DataNode
SecondaryNameNode
NodeManager
```

На `dn01.example.invalid` и `dn02.example.invalid`:

```text
DataNode
NodeManager
```

Для сдачи рекомендуется сохранить скриншот ResourceManager, на котором видны три активных NodeManager, и скриншот успешно выполненного задания.

---



## Шаг 12. Остановка и повторный запуск YARN

Если YARN необходимо остановить, выполнить на `nn.example.invalid`:

```bash
mapred --daemon stop historyserver
cd ~/hadoop-3.4.0
sbin/stop-yarn.sh
```

Для повторного запуска:

```bash
cd ~/hadoop-3.4.0
sbin/start-yarn.sh
mapred --daemon start historyserver
```

Проверить:

```bash
jps
yarn node -list -all
```

> **Важно:** остановка и запуск YARN не требуют повторного форматирования HDFS.

---



## Результат

После выполнения инструкции должен работать кластер:

```text
HDFS
├── 1 NameNode
├── 1 SecondaryNameNode
└── 3 DataNode

YARN
├── 1 ResourceManager
├── 3 NodeManager
└── 1 JobHistoryServer
```

Должны выполняться следующие условия:

- YARN успешно запущен;
- ResourceManager видит 3 NodeManager;
- тестовая MapReduce-задача выполняется;
- результат задачи записывается в HDFS;
- веб-интерфейс ResourceManager доступен;
- веб-интерфейс JobHistoryServer доступен;
- веб-интерфейсы NodeManager доступны;
- существующий HDFS-кластер из ДЗ №1 продолжает работать.

