# Ansible: учебный HDFS-кластер на четырёх Ubuntu VM

Проект автоматизирует `manual-installation.md` для **Apache Hadoop 3.4.0 / OpenJDK 11**. Топология из конспекта:

| Hostname | Частный IP | Службы |
|---|---|---|
| `edge.example.invalid` | `192.0.2.10` | DataNode #3, SecondaryNameNode, HDFS CLI |
| `nn.example.invalid` | `192.0.2.11` | NameNode |
| `dn01.example.invalid` | `192.0.2.12` | DataNode #1 |
| `dn02.example.invalid` | `192.0.2.13` | DataNode #2 |

Репликация: **3**. NameNode RPC: `nn.example.invalid:8020`. Веб-интерфейсы: `:9870` и `:9868`.

## Перед первым запуском

1. Зайдите **на edge**: `ssh cluster-admin@203.0.113.10`.
2. Убедитесь, что пользователь `cluster-admin` на edge может входить в остальные три VM ключом **`/home/cluster-admin/.ssh/cluster_ed25519`** и что `sudo -n true` работает на всех VM. Этот ключ существовал в исходных инструкциях; Ansible не создаёт его и не пересылает.
3. Установите Ansible на **edge** (для Ubuntu, если доступен системный пакет): `sudo apt update && sudo apt install -y ansible`.
4. Перенесите архив проекта на edge, распакуйте и перейдите в папку `hdfs-ansible`.
5. Проверка SSH: `ansible hadoop_cluster -m ping`.

**Запуск с ноутбука напрямую не предполагается**: только edge имеет внешний IP, а остальные узлы находятся в частной сети. В inventory для edge установлен `ansible_connection=local`; остальные три — по SSH из edge.

## Установка

```bash
ansible-playbook site.yml
ansible-playbook verify.yml
```

`site.yml` обновит пакеты apt, установит Java 11, создаст пользователя `hadoop`, скачает Hadoop на edge и разошлёт архив, создаст каталоги, сгенерирует XML/`workers`, настроит systemd, **один раз** отформатирует чистый NameNode и запустит службы в правильном порядке. Затем дождётся `Live datanodes (3)`.

`verify.yml` проверит три DataNode, загрузит и скачает тестовый файл, выполнит `hdfs fsck` и проверит репликацию.

### Повторный запуск и управление

```bash
ansible-playbook site.yml    # повторная настройка; форматирование не повторяется
ansible-playbook stop.yml    # остановка сервисов
ansible-playbook start.yml   # запуск без форматирования
ansible-playbook verify.yml  # проверка чтения/записи
```

Службы автоматически стартуют после перезагрузки VM благодаря systemd. Логи: `/home/hadoop/logs/` и `journalctl -u hdfs-namenode`, `journalctl -u hdfs-datanode`, `journalctl -u hdfs-secondarynamenode` на соответствующих машинах.

### Доступ к UI с ноутбука

```bash
ssh -N -L 9870:192.0.2.11:9870 cluster-admin@203.0.113.10
# http://localhost:9870

# В другом терминале:
ssh -N -L 9868:192.0.2.10:9868 cluster-admin@203.0.113.10
# http://localhost:9868
```

## Безопасность и отличие от ручных шагов

- **Не удаляйте** `/home/hadoop/hdfs/namenode` и `/home/hadoop/hdfs/datanode`. Повторный format существующего NameNode способен сделать блоки DataNode недоступными.
- Форматирование выполняется **только при отсутствии** `namenode/current/VERSION` и если каталог NameNode пуст. При неизвестном содержимом выполнение останавливается.
- Вместо обмена **одним приватным SSH-ключом hadoop** между четырьмя серверами используется Ansible через существующую учётку `cluster-admin`. Ключ `hadoop` не нужен: процессы управляются локально через systemd. Это безопаснее и не требует SSH-копирования между DataNode.
- Для пользователя `hadoop` создаётся учётная запись **без интерактивного пароля**. При необходимости пароль можно назначить отдельно, но для запуска Hadoop он не нужен.
- Файлы `/etc/hosts` фиксируют частные IP для разрешения имён, даже если внутренний DNS не настроен.
- Для простоты службы организованы как `systemd Type=simple` с запуском `hdfs namenode`, `hdfs datanode`, `hdfs secondarynamenode` в foreground. Это заменяет ручные `hdfs --daemon start ...`, позволяет перезапуск после reboot и не использует `start-dfs.sh`.
- В отличие от оригинала, Hadoop распаковывается **с одного скачанного архива** с Ansible-controller (edge) на узлы; интернет нужен только edge.
- Предполагается, что на Ubuntu доступен пакет `openjdk-11-jdk` и VM подходят по архитектуре (путь Java `...amd64`). Если apt не находит пакет, нужно подключить совместимый репозиторий или изменить версию Java/путь по совместимости с Hadoop.
- Это **учебный незащищённый HDFS** без Kerberos, TLS и HA. SecondaryNameNode выполняет checkpoint метаданных, **не является резервным NameNode**. Не открывайте порты HDFS в интернет.
- Параметры редактируются в `group_vars/all.yml`, IP и SSH — в `inventory/hosts.ini`. При изменении конфигурации уже работающие службы перезапускаются.

## Структура

```text
hdfs-ansible/
├── ansible.cfg
├── inventory/hosts.ini
├── group_vars/all.yml
├── site.yml
├── verify.yml
├── start.yml
├── stop.yml
└── roles/
    ├── common/tasks/main.yml
    └── hadoop/
        ├── tasks/main.yml
        ├── handlers/main.yml
        └── templates/{core-site.xml.j2,hdfs-site.xml.j2,workers.j2,hdfs.service.j2}
```
