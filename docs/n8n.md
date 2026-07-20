# Интеграция с n8n

## Сеть

Создайте общую сеть один раз:

```bash
docker network create automation
```

Подключите к ней n8n и `privacy-filter`. API не публикует порт на хост и доступен из n8n по адресу `http://privacy-filter:8000/v1/redact`.

## Credential

В n8n создайте credential типа `Header Auth`:

- Name: `Authorization`
- Value: `Bearer <значение Docker secret>`

Не вставляйте токен непосредственно в workflow.

## HTTP Request node

- Method: `POST`
- URL: `http://privacy-filter:8000/v1/redact`
- Authentication: `Generic Credential Type` -> `Header Auth`
- Content-Type: `application/json`
- Timeout: `300000` ms для CPU-пилота
- Body:

```json
{
  "text": "{{ $json.resume_text }}",
  "mode": "typed",
  "policy": "ru_resume"
}
```

В AI-узел передавайте только `{{ $json.redacted_text }}`. Перед ним добавьте `IF` с условием `{{ $json.summary.pii_check_passed }}`. Ветка `false` должна завершать workflow или отправлять документ на ручную проверку.

## Execution data

Для отдельного n8n-инстанса с чувствительными данными:

```yaml
environment:
  EXECUTIONS_DATA_SAVE_ON_SUCCESS: none
  EXECUTIONS_DATA_SAVE_ON_ERROR: none
  EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS: "false"
  EXECUTIONS_DATA_SAVE_ON_PROGRESS: "false"
```

Импортируемый синтетический пример находится в `deploy/n8n-http-request.workflow.json`. После импорта выберите созданный Header Auth credential.

