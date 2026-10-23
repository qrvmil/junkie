# Подключение к рабочему компьютеру

**Сервер:** `https://headscale.example.invalid`
**Токен:** `${HEADSCALE_AUTH_KEY}`
**Комп:** IP `192.0.2.20`, пользователь `student`

> Ставь клиент только по ссылкам ниже. Версии из apt/snap бывают старые и не подключаются.

---

## Windows

Скачай и установи клиент: **https://tailscale.com/download/windows**
Открой PowerShell **от администратора**:
```
tailscale up --login-server=https://headscale.example.invalid --authkey=${HEADSCALE_AUTH_KEY}
```

## Ubuntu

Установка:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Запуск:

```bash
sudo tailscale up --login-server=https://headscale.example.invalid --authkey=${HEADSCALE_AUTH_KEY}
```
> Если стоял snap: сначала `sudo snap remove tailscale`.

## macOS

Установка:

```bash
brew install tailscale
sudo brew services start tailscale
```

Запуск:

```bash
sudo tailscale up --login-server=https://headscale.example.invalid --authkey=${HEADSCALE_AUTH_KEY} --accept-dns=false
```

---

## Проверка и подключение

```bash
tailscale status          # в списке должен быть example-workstation
ssh student@192.0.2.20        # заходишь на комп
```
Jupyter (если нужен): открой в браузере `http://192.0.2.20:8888`
