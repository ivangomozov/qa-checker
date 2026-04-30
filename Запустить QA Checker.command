#!/bin/bash

# Переходим в папку со скриптом (где бы она ни лежала)
cd "$(dirname "$0")"

# Проверяем что python3 есть
if ! command -v python3 &> /dev/null; then
  osascript -e 'display alert "Python 3 не найден" message "Установи Python 3 с python.org и попробуй снова."'
  exit 1
fi

# Проверяем что Flask установлен
if ! python3 -c "import flask" &> /dev/null; then
  osascript -e 'display alert "Flask не установлен" message "Открой Терминал и выполни: pip3 install -r requirements.txt"'
  exit 1
fi

# Запускаем сервер в фоне
python3 app.py &
SERVER_PID=$!

# Ждём пока сервер поднимется
sleep 2

# Открываем браузер
open http://localhost:5050

# Показываем уведомление
osascript -e 'display notification "QA Checker запущен на localhost:5050" with title "QA Checker" sound name "Morse"'

# Ждём завершения сервера
wait $SERVER_PID
