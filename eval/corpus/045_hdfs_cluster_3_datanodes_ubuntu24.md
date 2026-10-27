# Развёртывание учебного кластера HDFS 3.4.0 на Ubuntu 24.04 (3 DataNode)

> **Область применения:** учебный кластер из четырёх Ubuntu VM, без Kerberos, высокой доступности (HA), YARN и автоматизации конфигурации. Все команды приводятся для последовательного ручного выполнения.  
> **Важно:** убедитесь, что у вас есть разрешение администрировать все четыре VM. Не запускайте `namenode -format` на существующем кластере с данными.

## 0. Исходное состояние и целевая архитектура

Преподаватель выдал **четыре отдельных виртуальных машины** (не четыре терминала одной ОС). Они соединены частной сетью `192.0.2.0/...`. Из интернета напрямую доступна только **edge-нода** с внешним IP `203.0.113.10`. На всех VM исходно есть пользователь `cluster-admin`, способный выполнить `sudo` без пароля.

| VM | Имя DNS/hostname | Приватный IP | Планируемые службы |
|---|---|---|---|
| Edge | `edge.example.invalid` | `192.0.2.10` | **DataNode №3**, **SecondaryNameNode**, клиентские команды HDFS |
| NameNode | `nn.example.invalid` | `192.0.2.11` | **NameNode** |
| DataNode №1 | `dn01.example.invalid` | `192.0.2.12` | **DataNode №1** |
| DataNode №2 | `dn02.example.invalid` | `192.0.2.13` | **DataNode №2** |

**Почему DataNode на edge?** Имеется всего четыре VM, а нужны один отдельный NameNode и три DataNode. Поэтому один DataNode совмещаем с edge. SecondaryNameNode разместим там же. Это компромисс для лабораторной работы: edge будет дополнительно нагружен хранением блоков. Если появится пятая VM, третий DataNode разумнее перенести туда.

**Роли:** NameNode хранит метаданные и расположение блоков; DataNode хранят сами блоки; SecondaryNameNode периодически создаёт контрольные точки метаданных, **но не является запасным NameNode и не выполняет автоматический failover**. Для работы HDFS SecondaryNameNode не строго обязателен, однако включён по требованию задания.

Схема:

```text
Ваш ноутбук
     |
     | ssh cluster-admin@203.0.113.10
     v
Edge: edge.example.invalid (192.0.2.10) ----------------------+
  - DataNode #3                                      | внутренняя сеть
  - SecondaryNameNode                                |
  - Hadoop CLI                                       |
     |                  |                            |
     +--> nn.example.invalid   +--> dn01.example.invalid      +--> dn02.example.invalid
          192.0.2.11        192.0.2.12           192.0.2.13
          NameNode          DataNode #1          DataNode #2
```

**Соглашение в командах:** `cluster-admin` используется для начального администрирования и `sudo`, `hadoop` — для запуска процессов Hadoop. Там, где написано «на edge под cluster-admin», перед выполнением убедитесь в `whoami` и `hostname`. В командах ниже имя первого DataNode — именно `dn01.example.invalid` (две цифры ноль), сверяйте с действительным `hostname`.

---

## Шаг 0. Подключение и обновление Ubuntu на всех VM

### 0.1. С локального компьютера войти на edge

```bash
ssh cluster-admin@203.0.113.10
whoami
hostname
```

Ожидается `cluster-admin` и `edge.example.invalid`.

Обновить пакеты **на edge**:

```bash
sudo apt update
sudo apt upgrade
```

Если система сообщает, что требуется перезагрузка после обновления ядра, согласуйте окно перезагрузки с командой. После `sudo reboot` SSH-сессия завершится; заново подключитесь к edge.

### 0.2. NameNode

На **edge**:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid
whoami
hostname
sudo apt update
sudo apt upgrade
exit
```

`exit` возвращает на edge. Проверить: `hostname` → `edge.example.invalid`.

### 0.3. DataNode №1

На **edge**:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn01.example.invalid
whoami
hostname
sudo apt update
sudo apt upgrade
exit
```

### 0.4. DataNode №2

На **edge**:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn02.example.invalid
whoami
hostname
sudo apt update
sudo apt upgrade
exit
```

**Замечание:** если вы находитесь на NameNode и хотите попасть на другой внутренний узел, сначала выполните `exit`, чтобы вернуться на edge, либо начните новое подключение явно. Это правило относится к *вашему существующему ключу* `cluster_ed25519`, который расположен на edge, а не является обязательным правилом всей сети.

---

## Шаг 1. Создать системного пользователя `hadoop` на каждой VM

> Команда `sudo -iu hadoop` **не создаёт** пользователя. Она переключает в уже существующую учётную запись. Для создания используется `sudo adduser hadoop` (два `d`).

### 1.1. Edge

Под `cluster-admin` на edge:

```bash
sudo adduser hadoop
id hadoop
getent passwd hadoop
```

Задайте пароль в интерактивном диалоге; поля Full Name, Room Number, Work Phone, Home Phone, Other можно оставить пустыми. Простой пароль не используйте. **Одинаковый пароль на всех узлах не требуется**: далее SSH будет работать по ключу.

### 1.2. NameNode

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid
sudo adduser hadoop
id hadoop
exit
```

### 1.3. DataNode №1

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn01.example.invalid
sudo adduser hadoop
id hadoop
exit
```

### 1.4. DataNode №2

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn02.example.invalid
sudo adduser hadoop
id hadoop
exit
```

Проверка на edge:

```bash
sudo -iu hadoop
whoami
pwd
exit
```

Ожидается `hadoop`, `/home/hadoop`. **Не добавляем `hadoop` в sudoers**: службы HDFS запускаются обычным пользователем.

---

## Шаг 2. Проверить имена и сеть между VM

На edge под `cluster-admin`:

```bash
getent hosts edge.example.invalid
getent hosts nn.example.invalid
getent hosts dn01.example.invalid
getent hosts dn02.example.invalid
```

Ожидаются соответствующие адреса `192.0.2.10`–`192.0.2.13`. Если имена уже разрешаются правильно, **не меняйте** `/etc/hosts`.

При необходимости на **каждой** VM открыть `/etc/hosts` с `sudo nano /etc/hosts` и добавить (не удаляя строку `127.0.0.1 localhost`):

```text
192.0.2.10 edge.example.invalid
192.0.2.11 nn.example.invalid
192.0.2.12 dn01.example.invalid
192.0.2.13 dn02.example.invalid
```

После изменения проверить `getent hosts ...` на всех VM. Критично, чтобы имена не разрешались только в `127.0.1.1` при обращении с других VM.

Проверка сети из edge:

```bash
ping -c 2 nn.example.invalid
ping -c 2 dn01.example.invalid
ping -c 2 dn02.example.invalid
```

Если ICMP заблокирован, не делайте вывод, что весь доступ не работает: проверьте хотя бы SSH. Внутренние узлы должны иметь возможность связываться по TCP с NameNode (в частности, порт `8020`) и друг с другом по портам HDFS DataNode (по умолчанию `9866`, `9867`; web UI `9864`). Не открывайте эти порты в публичный интернет.

---

## Шаг 3. Настроить SSH для пользователя `hadoop`

Для максимальной простоты в **данной учебной инструкции** создаём одну SSH-пару на edge под `hadoop`, затем копируем её на четыре VM. Это даёт SSH-доступ `hadoop → hadoop` между всеми узлами при разрешённой сетевой связности.

**Ограничение безопасности:** приватный ключ оказывается на нескольких хостах; компрометация одного из них позволяет использовать этот ключ на остальных. На production кластерах предпочтительнее отдельные ключи для каждого хоста или централизованная аутентификация. Не копируйте приватный ключ на свой ноутбук и не публикуйте его в Git.

### 3.1. На edge сгенерировать пару под `hadoop`

На edge под `cluster-admin`:

```bash
sudo -iu hadoop
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
ls -la ~/.ssh
exit
```

`-N ""` — без парольной фразы для неинтерактивного запуска скриптов Hadoop. `authorized_keys` хранит **публичный**, а не приватный ключ.

### 3.2. Скопировать `.ssh` с edge на NameNode

На edge под `cluster-admin`:

```bash
sudo tar -C /home/hadoop -cf - .ssh | \
  ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid \
  'sudo tar -C /home/hadoop -xpf - && sudo chown -R hadoop:hadoop /home/hadoop/.ssh'
```

### 3.3. Скопировать `.ssh` на DataNode №1

```bash
sudo tar -C /home/hadoop -cf - .ssh | \
  ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn01.example.invalid \
  'sudo tar -C /home/hadoop -xpf - && sudo chown -R hadoop:hadoop /home/hadoop/.ssh'
```

### 3.4. Скопировать `.ssh` на DataNode №2

```bash
sudo tar -C /home/hadoop -cf - .ssh | \
  ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn02.example.invalid \
  'sudo tar -C /home/hadoop -xpf - && sudo chown -R hadoop:hadoop /home/hadoop/.ssh'
```

Эти команды предназначены для **новых, пустых** каталогов `.ssh` пользователя `hadoop` на целевых VM. Они могут перезаписать файлы с совпадающими именами. Сохранение исходного владельца при распаковке зависит от конфигурации `tar` и UID; дополнительный `chown` делает результат предсказуемым. Убедитесь, что `/home/hadoop` существует на всех узлах.

### 3.5. Проверить права на целевых узлах

На edge под `cluster-admin`, последовательно:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid
sudo chmod 700 /home/hadoop/.ssh
sudo chmod 600 /home/hadoop/.ssh/id_ed25519 /home/hadoop/.ssh/authorized_keys
sudo chmod 644 /home/hadoop/.ssh/id_ed25519.pub
sudo ls -l /home/hadoop/.ssh
exit
```

Аналогично на `dn01.example.invalid` и `dn02.example.invalid` (повторить эти же команды, меняя только SSH-адрес).

### 3.6. Проверить беспарольное подключение

С edge:

```bash
sudo -iu hadoop
ssh hadoop@edge.example.invalid hostname
ssh hadoop@nn.example.invalid hostname
ssh hadoop@dn01.example.invalid hostname
ssh hadoop@dn02.example.invalid hostname
```

Первое подключение к каждому адресу может запросить подтверждение отпечатка **ключа SSH-сервера**. Проверяйте отпечаток доверенным способом и только затем подтверждайте `yes`. **Пароль учётной записи `hadoop` вводиться не должен**.

Проверка в неинтерактивном режиме после принятия ключей хостов:

```bash
ssh -o BatchMode=yes hadoop@nn.example.invalid hostname
ssh -o BatchMode=yes hadoop@dn01.example.invalid hostname
ssh -o BatchMode=yes hadoop@dn02.example.invalid hostname
exit
```

Для гарантии подключения **из NameNode** (именно там мы будем запускать `start-dfs.sh`):

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid
sudo -iu hadoop
ssh hadoop@nn.example.invalid hostname
ssh hadoop@edge.example.invalid hostname
ssh hadoop@dn01.example.invalid hostname
ssh hadoop@dn02.example.invalid hostname
exit
exit
```

Оба `exit` возвращают на edge под `cluster-admin`. На всякий случай: `hostname`.

---

## Шаг 4. Установить Java 11 на все четыре VM

Для Hadoop 3.4.0 выбираем **OpenJDK 11** — поддерживаемую версию JRE/JDK для ветки Hadoop 3.3/3.4. Ubuntu 24.04 может не иметь `openjdk-11-jdk` в подключённых по умолчанию репозиториях; сначала проверьте наличие пакета. **Если `apt` не находит Java 11 — не заменяйте её молча на Java 21**: используйте согласованный с курсом дистрибутив JDK 11 (например, Temurin 11) на всех узлах.

На edge:

```bash
sudo apt update
apt-cache policy openjdk-11-jdk
sudo apt install openjdk-11-jdk
java -version
readlink -f "$(command -v java)"
```

Если пакет недоступен, см. примечание выше; последующие команды предполагают, что Java 11 уже установлена на всех узлах. Типичный путь при Ubuntu-пакете: `/usr/lib/jvm/java-11-openjdk-amd64` (для ARM — другой).

На NameNode:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid
sudo apt update
sudo apt install openjdk-11-jdk
java -version
exit
```

На DataNode №1:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn01.example.invalid
sudo apt update
sudo apt install openjdk-11-jdk
java -version
exit
```

На DataNode №2:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn02.example.invalid
sudo apt update
sudo apt install openjdk-11-jdk
java -version
exit
```

Проверка `java -version`: ожидается версия `11.x` на **каждом** узле. Убедитесь, что `JAVA_HOME` для запускаемого `java` соответствует фактическому пути JDK (например, `dirname "$(dirname "$(readlink -f "$(command -v java)")")"`).

---

## Шаг 5. Скачать бинарный дистрибутив Hadoop 3.4.0 на edge

**Важное исправление исходной ссылки:** файл `hadoop-3.4.0-src.tar.gz` — это **исходный код**, который требует сборки. Для установки скачиваем бинарный архив **`hadoop-3.4.0.tar.gz`**. Поскольку выпуск исторический, надёжная ссылка — `archive.apache.org`, а не текущий `dlcdn.apache.org`.

Официальные страницы: https://hadoop.apache.org/releases.html и https://archive.apache.org/dist/hadoop/common/hadoop-3.4.0/.

На edge под `cluster-admin`:

```bash
sudo -iu hadoop
cd ~
wget https://archive.apache.org/dist/hadoop/common/hadoop-3.4.0/hadoop-3.4.0.tar.gz
wget https://archive.apache.org/dist/hadoop/common/hadoop-3.4.0/hadoop-3.4.0.tar.gz.sha512
sha512sum -c hadoop-3.4.0.tar.gz.sha512
```

Если файл контрольной суммы имеет особый формат, который `sha512sum -c` не распознаёт, сравните выведенный `sha512sum hadoop-3.4.0.tar.gz` с контрольной суммой с сайта Apache вручную. Не продолжайте при несовпадении.

```bash
tar -xzf hadoop-3.4.0.tar.gz
ls -ld ~/hadoop-3.4.0
ls ~/hadoop-3.4.0/etc/hadoop
exit
```

**Объём:** бинарный архив около 921 МБ, распакованное дерево потребует больше места. Проверьте `df -h /home` заранее.

---

## Шаг 6. Перенести установленный Hadoop с edge на остальные VM

Будем копировать уже распакованную директорию. Действия **все ещё под `cluster-admin` на edge**; `sudo tar` читает файлы `hadoop`, на удалённых узлах `sudo tar` записывает их в `/home/hadoop`. Для корректного владельца укажем явный `chown` после распаковки.

### NameNode

```bash
sudo tar -C /home/hadoop -cf - hadoop-3.4.0 | \
  ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid \
  'sudo tar -C /home/hadoop -xpf - && sudo chown -R hadoop:hadoop /home/hadoop/hadoop-3.4.0'
```

### DataNode №1

```bash
sudo tar -C /home/hadoop -cf - hadoop-3.4.0 | \
  ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn01.example.invalid \
  'sudo tar -C /home/hadoop -xpf - && sudo chown -R hadoop:hadoop /home/hadoop/hadoop-3.4.0'
```

### DataNode №2

```bash
sudo tar -C /home/hadoop -cf - hadoop-3.4.0 | \
  ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn02.example.invalid \
  'sudo tar -C /home/hadoop -xpf - && sudo chown -R hadoop:hadoop /home/hadoop/hadoop-3.4.0'
```

**Не прерывайте** копирование посередине. При ошибках сети повторите команду после проверки места `df -h` и отсутствия запущенных процессов Hadoop. Этот метод для лабораторной работы, не инструмент обновления работающего production-кластера.

---

## Шаг 7. Настроить переменные окружения и пути

Настроим вначале **edge**, затем аналогично остальные VM. Все пути здесь предполагают `/home/hadoop/hadoop-3.4.0`.

### 7.1. Edge

```bash
sudo -iu hadoop
nano ~/.bashrc
```

В конец файла дописать:

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/home/hadoop/hadoop-3.4.0
export HADOOP_CONF_DIR=$HADOOP_HOME/etc/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
```

**Замените JAVA_HOME фактическим путём**, если `readlink` из Шага 4 вернул иной JDK. Применить:

```bash
source ~/.bashrc
printf '%s\n' "$JAVA_HOME" "$HADOOP_HOME"
hadoop version
exit
```

### 7.2. NameNode

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid
sudo -iu hadoop
nano ~/.bashrc
```

Допишите **те же четыре строки**, сохраните файл, выполните:

```bash
source ~/.bashrc
hadoop version
exit
exit
```

### 7.3. DataNode №1

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn01.example.invalid
sudo -iu hadoop
nano ~/.bashrc
```

Допишите те же строки, затем:

```bash
source ~/.bashrc
hadoop version
exit
exit
```

### 7.4. DataNode №2

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn02.example.invalid
sudo -iu hadoop
nano ~/.bashrc
```

Допишите те же строки, затем:

```bash
source ~/.bashrc
hadoop version
exit
exit
```

**Почему одного `.bashrc` недостаточно для демонов?** При запуске через SSH не все shell-сеансы читают `.bashrc`. Поэтому обязательно зададим `JAVA_HOME` ещё и в `hadoop-env.sh` — см. далее.

---

## Шаг 8. Создать локальные каталоги для данных HDFS

Это **обычные локальные директории Linux**, не HDFS-пути. NameNode хранит там метаданные, DataNode — блоки.

### 8.1. На NameNode

На edge под `cluster-admin`:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid
sudo install -d -m 700 -o hadoop -g hadoop /home/hadoop/hdfs/namenode
ls -ld /home/hadoop/hdfs/namenode
exit
```

### 8.2. На каждом DataNode (включая edge)

Edge:

```bash
sudo install -d -m 700 -o hadoop -g hadoop /home/hadoop/hdfs/datanode
```

DataNode №1:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn01.example.invalid
sudo install -d -m 700 -o hadoop -g hadoop /home/hadoop/hdfs/datanode
exit
```

DataNode №2:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn02.example.invalid
sudo install -d -m 700 -o hadoop -g hadoop /home/hadoop/hdfs/datanode
exit
```

**Нельзя** на рабочем кластере удалять или очищать эти каталоги произвольно.

---

## Шаг 9. Настроить Hadoop XML-конфигурацию на edge

Удобно создать единую конфигурацию на **edge под `hadoop`**, а затем скопировать её на остальные узлы. Она указывает, где находится NameNode, какие узлы запускают DataNode и где располагать локальные данные.

```bash
sudo -iu hadoop
cd ~/hadoop-3.4.0/etc/hadoop
```

### 9.1. `hadoop-env.sh`

```bash
nano hadoop-env.sh
```

Найдите `export JAVA_HOME=` и установите **фактический** путь из Шага 4 (не добавляйте противоречащих друг другу активных определений):

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
```

### 9.2. `core-site.xml`

```bash
nano core-site.xml
```

Укажите:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>
<configuration>
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://nn.example.invalid:8020</value>
  </property>
</configuration>
```

`fs.defaultFS` сообщает клиентам, где искать HDFS NameNode. Имя `nn.example.invalid` должно разрешаться **на каждой VM**.

### 9.3. `hdfs-site.xml`

```bash
nano hdfs-site.xml
```

Вставьте:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>
<configuration>
  <property>
    <name>dfs.replication</name>
    <value>3</value>
  </property>
  <property>
    <name>dfs.namenode.name.dir</name>
    <value>file:///home/hadoop/hdfs/namenode</value>
  </property>
  <property>
    <name>dfs.datanode.data.dir</name>
    <value>file:///home/hadoop/hdfs/datanode</value>
  </property>
  <property>
    <name>dfs.namenode.secondary.http-address</name>
    <value>edge.example.invalid:9868</value>
  </property>
</configuration>
```

- `dfs.replication=3` создаёт три реплики новых файлов при наличии трёх исправных DataNode.
- `dfs.namenode.name.dir` фактически использует только NameNode.
- `dfs.datanode.data.dir` используется тремя DataNode.
- `dfs.namenode.secondary.http-address` задаёт адрес веб-интерфейса SecondaryNameNode. Для учебного кластера дополнительно разместим его на edge.

### 9.4. `workers`

```bash
nano workers
```

Заменить содержимое:

```text
edge.example.invalid
dn01.example.invalid
dn02.example.invalid
```

В файле **три DataNode**, а `nn.example.invalid` здесь отсутствует. Файл `workers` используется shell-скриптами вроде `start-dfs.sh` для запуска процессов по SSH; это **не база зарегистрированных DataNode**.

Проверить, что файлы сохранены:

```bash
cat workers
cat core-site.xml
cat hdfs-site.xml
exit
```

---

## Шаг 10. Перенести одинаковую конфигурацию на NameNode и DataNode

На edge под `cluster-admin`. **Не копируем** каталог HDFS с блоками или метаданными: только `etc/hadoop`.

### 10.1. NameNode

```bash
sudo tar -C /home/hadoop/hadoop-3.4.0 -cf - etc/hadoop | \
  ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid \
  'sudo tar -C /home/hadoop/hadoop-3.4.0 -xpf - && sudo chown -R hadoop:hadoop /home/hadoop/hadoop-3.4.0/etc/hadoop'
```

### 10.2. DataNode №1

```bash
sudo tar -C /home/hadoop/hadoop-3.4.0 -cf - etc/hadoop | \
  ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn01.example.invalid \
  'sudo tar -C /home/hadoop/hadoop-3.4.0 -xpf - && sudo chown -R hadoop:hadoop /home/hadoop/hadoop-3.4.0/etc/hadoop'
```

### 10.3. DataNode №2

```bash
sudo tar -C /home/hadoop/hadoop-3.4.0 -cf - etc/hadoop | \
  ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn02.example.invalid \
  'sudo tar -C /home/hadoop/hadoop-3.4.0 -xpf - && sudo chown -R hadoop:hadoop /home/hadoop/hadoop-3.4.0/etc/hadoop'
```

Если Java установлена по **разным путям**, после копирования поправьте `hadoop-env.sh` на соответствующей VM. Процессы должны использовать корректный `JAVA_HOME`.

---

## Шаг 11. Один раз отформатировать НОВЫЙ NameNode

> **ОПАСНО ДЛЯ СУЩЕСТВУЮЩИХ ДАННЫХ.** `hdfs namenode -format` делают **один раз при создании нового HDFS**. Никогда не повторяйте его при обычном перезапуске, ошибках запуска или обновлении. Повторное форматирование может сделать прежние данные HDFS недоступными.

Убедитесь, что это **новый пустой** кластер. На edge под `cluster-admin`:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid
sudo -iu hadoop
source ~/.bashrc
hdfs namenode -format
```

Проверьте вывод: успешное создание хранилища метаданных и отсутствие ошибок. **Не используйте опцию `-force`**.

```bash
exit
exit
```

Снова на edge под `cluster-admin`.

---

## Шаг 12. Запустить HDFS и SecondaryNameNode

Чтобы исключить разночтения с расположением SecondaryNameNode, запустим службы **вручную на нужных VM**. Это показывает, где реально работают демоны, и не зависит от автоматического выбора SecondaryNameNode скриптом.

### 12.1. NameNode (только `nn.example.invalid`)

На edge:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid
sudo -iu hadoop
source ~/.bashrc
hdfs --daemon start namenode
jps
exit
exit
```

Ожидается Java-процесс `NameNode`.

### 12.2. DataNode №3 на edge

```bash
sudo -iu hadoop
source ~/.bashrc
hdfs --daemon start datanode
jps
exit
```

### 12.3. DataNode №1

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn01.example.invalid
sudo -iu hadoop
source ~/.bashrc
hdfs --daemon start datanode
jps
exit
exit
```

### 12.4. DataNode №2

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn02.example.invalid
sudo -iu hadoop
source ~/.bashrc
hdfs --daemon start datanode
jps
exit
exit
```

### 12.5. SecondaryNameNode на edge

```bash
sudo -iu hadoop
source ~/.bashrc
hdfs --daemon start secondarynamenode
jps
exit
```

На edge ожидаются **DataNode** и **SecondaryNameNode**; на `nn.example.invalid` — **NameNode**; на каждом из `dn01.example.invalid` и `dn02.example.invalid` — **DataNode**. `jps` может показывать также сам `Jps`.

**Примечание про `start-dfs.sh`:** он запускает NameNode на текущем узле, DataNode — на узлах из `workers` по SSH, а SecondaryNameNode — на узлах, которые определяет конфигурация. После проверки конфигурации можно запускать его с NameNode под `hadoop`, но для учебного ручного первого старта приведённый поузловой способ прозрачнее.

---

## Шаг 13. Проверить работоспособность HDFS

### 13.1. Отчёт о DataNode

На edge:

```bash
sudo -iu hadoop
source ~/.bashrc
hdfs dfsadmin -report
```

Ожидается `Live datanodes (3)` и три узла. **Если 2 или меньше — пока не продолжайте** с тестом репликации: найдите ошибку подключения, прав на каталог, Java или конфигурации.

Дополнительно:

```bash
hdfs dfs -ls /
hdfs dfsadmin -safemode get
```

### 13.2. Создать файл в HDFS и скачать обратно

На edge под `hadoop`:

```bash
printf 'Hello from HDFS!\n' > ~/hdfs-test.txt
hdfs dfs -mkdir -p /user/hadoop
hdfs dfs -put ~/hdfs-test.txt /user/hadoop/
hdfs dfs -ls /user/hadoop/
hdfs dfs -cat /user/hadoop/hdfs-test.txt
hdfs dfs -get /user/hadoop/hdfs-test.txt ~/hdfs-test-from-cluster.txt
cat ~/hdfs-test-from-cluster.txt
```

`~/hdfs-test.txt` — **локальный файл edge**. `/user/hadoop/hdfs-test.txt` — **файл в HDFS**. Это две разные файловые системы.

Проверить репликацию и расположение блоков:

```bash
hdfs fsck /user/hadoop/hdfs-test.txt -files -blocks -locations
```

Ожидается `HEALTHY` и три расположения (реплики) блока, если все DataNode живы и репликация успела завершиться.

### 13.3. Веб-интерфейсы

По умолчанию NameNode HTTP UI: `http://nn.example.invalid:9870`, SecondaryNameNode: `http://edge.example.invalid:9868`. Эти приватные DNS-имена могут не открываться на вашем ноутбуке напрямую.

Для доступа к **NameNode UI** с ноутбука используйте туннель (запускать **на ноутбуке**, не на VM):

```bash
ssh -N -L 9870:192.0.2.11:9870 cluster-admin@203.0.113.10
```

Откройте в браузере ноутбука: `http://localhost:9870`. SSH-туннель оставьте активным до окончания просмотра. Порт на ноутбуке должен быть свободен. Не публикуйте административный UI в интернете.

Для SecondaryNameNode UI (другой терминал ноутбука):

```bash
ssh -N -L 9868:192.0.2.10:9868 cluster-admin@203.0.113.10
```

Откройте `http://localhost:9868`. Если UI не открывается, проверьте, слушает ли служба нужный адрес, например `ss -lnt | grep 9868` на edge.

```bash
exit
```

---

## Шаг 14. Как корректно останавливать и снова запускать HDFS

**Важно:** не форматировать NameNode повторно.

Останавливать удобно сначала SecondaryNameNode, потом DataNode, затем NameNode. Все команды выполняются **под `hadoop`** на соответствующих хостах.

На edge:

```bash
sudo -iu hadoop
source ~/.bashrc
hdfs --daemon stop secondarynamenode
hdfs --daemon stop datanode
exit
```

DataNode №1:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn01.example.invalid
sudo -iu hadoop
source ~/.bashrc
hdfs --daemon stop datanode
exit
exit
```

DataNode №2:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@dn02.example.invalid
sudo -iu hadoop
source ~/.bashrc
hdfs --daemon stop datanode
exit
exit
```

NameNode:

```bash
ssh -i /home/cluster-admin/.ssh/cluster_ed25519 cluster-admin@nn.example.invalid
sudo -iu hadoop
source ~/.bashrc
hdfs --daemon stop namenode
exit
exit
```

Для последующего запуска **повторить Шаг 12 без Шага 11**. Проверьте `hdfs dfsadmin -report`.

---

## Шаг 15. Если что-то пошло не так

**Ошибка `Permission denied (publickey)` при SSH `hadoop`:**

```bash
whoami
ls -ld ~/.ssh
ls -l ~/.ssh/authorized_keys ~/.ssh/id_ed25519
ssh -v hadoop@nn.example.invalid hostname
```

Проверяйте, что команду запускаете именно под `hadoop`, файл приватного ключа существует, каталог принадлежит `hadoop`, публичный ключ есть в `authorized_keys` на сервере назначения. Серверные журналы: `sudo journalctl -u ssh -n 100 --no-pager` (имя systemd-юнита может различаться).

**Ошибка `JAVA_HOME is not set`:** проверяйте переменную в `~/hadoop-3.4.0/etc/hadoop/hadoop-env.sh` **на проблемной VM** и наличие установленного JDK в указанном пути.

**`Live datanodes (0/1/2)` вместо 3:**

```bash
jps
ls -lt ~/hadoop-3.4.0/logs | head
```

На нужной VM под `hadoop` прочитайте последние строки соответствующего `hadoop-hadoop-datanode-*.log` и проверьте `getent hosts nn.example.invalid`, доступ к `nn.example.invalid:8020`, права на `/home/hadoop/hdfs/datanode`.

**NameNode запускается, но HDFS остаётся в safe mode:** сначала убедитесь, что все три DataNode зарегистрировались, через `hdfs dfsadmin -report`, и только затем изучайте причину. Не отключайте safe mode принудительно для маскировки неисправности.

**`Connection refused` на 9870/9868:** соответствующий демон мог не запуститься либо слушает другой интерфейс. Проверьте `jps`, `ss -lnt`, логи и SSH-туннель.

**Недоступна Java 11 в `apt` Ubuntu 24.04:** установите Java 11 из согласованного официального поставщика JDK, настройте одинаковый `JAVA_HOME` на всех узлах. Не используйте случайные PPA и не смешивайте Java 11/21 без проверки совместимости.

**Файл есть в HDFS, но репликация меньше 3:** наличие трёх VM с DataNode ещё не гарантирует три готовые реплики. Проверить `hdfs fsck ... -locations`, `hdfs dfsadmin -report`, состояние DataNode и доступное место.

---

## Итоговый чек-лист

- [ ] Подключение с ноутбука на edge работает.
- [ ] На каждой из четырёх VM создан `hadoop`.
- [ ] Имена `*.example.invalid` корректно разрешаются между VM.
- [ ] Беспарольный SSH `hadoop` с NameNode на три DataNode и edge работает.
- [ ] Java 11 и бинарный Hadoop 3.4.0 установлены на каждой VM.
- [ ] `core-site.xml`, `hdfs-site.xml`, `workers`, `hadoop-env.sh` согласованы.
- [ ] NameNode отформатирован **только один раз**.
- [ ] `jps`: 1 NameNode, 1 SecondaryNameNode, 3 DataNode на заданных узлах.
- [ ] `hdfs dfsadmin -report` показывает **Live datanodes (3)**.
- [ ] `hdfs dfs -put` и `hdfs dfs -cat` работают.
- [ ] `hdfs fsck` показывает корректную репликацию.
- [ ] Веб-интерфейс NameNode открывается через SSH-туннель.

## Официальная документация

1. [Hadoop 3.4.0 — Cluster Setup](https://hadoop.apache.org/docs/r3.4.0/hadoop-project-dist/hadoop-common/ClusterSetup.html)
2. [Hadoop 3.4.0 — HDFS Architecture](https://hadoop.apache.org/docs/r3.4.0/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html)
3. [Hadoop 3.4.0 — Single Node Setup](https://hadoop.apache.org/docs/r3.4.0/hadoop-project-dist/hadoop-common/SingleCluster.html)
4. [Apache archive: Hadoop 3.4.0](https://archive.apache.org/dist/hadoop/common/hadoop-3.4.0/)
5. [Hadoop Java Versions](https://cwiki.apache.org/confluence/display/HADOOP/Hadoop+Java+Versions)

**Версионное примечание:** Hadoop 3.4.0 — фиксированная версия курса, а не актуальный рекомендуемый релиз. Инструкция демонстрирует базовую, незащищённую HDFS-топологию для изолированной учебной сети. Для эксплуатации с реальными данными требуются отдельное проектирование безопасности, резервного копирования и HA.
