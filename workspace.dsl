workspace {
    !identifiers hierarchical

    model {
        user = person "Пользователь" "Планирует мероприятия, получает напоминания, участвует в прогнозе"
        admin = person "Администратор" "Управляет системой и следит за корректностью данных"

        database = softwareSystem "PostgreSQL Database" {
            description "Хранит данные пользователей, мероприятий и чек-листов"
        }

        system = softwareSystem "Система планирования мероприятий" {
            description "Кроссплатформенное приложение для организации мероприятий"

            mobile_app = container "Мобильное приложение" {
                description "Позволяет пользователям создавать события, получать чек-листы и уведомления"
                technology "Flutter"
            }

            helper_bot = container "Helper Bot Service" {
                description "Генерация чек-листов и отправка напоминаний"
                technology "Python, Flask, OpenAI API, Firebase FCM"

                ChecklistController = component "ChecklistController" {
                    description "Обрабатывает запросы генерации чек-листа и отправки уведомлений"
                    technology "Flask"
                }
            }

            people_prediction = container "People Prediction Service" {
                description "Предсказание участия пользователя в мероприятии"
                technology "Python, CatBoost, pandas, sklearn"

                PredictionModule = component "PredictionModule" {
                    description "Обработка данных и обучение модели"
                    technology "CatBoost, pandas"
                }
            }

            mobile_app -> helper_bot "Запрос на чек-лист и уведомления" "HTTP POST /schedule_event"
            helper_bot -> "OpenAI API" "Запрос на генерацию чек-листа"
            helper_bot -> "Firebase FCM" "Отправка push-уведомлений"

            mobile_app -> people_prediction "Отправка данных на предсказание участия"
            people_prediction -> people_prediction.PredictionModule "Инференс модели"

            helper_bot -> database "Сохраняет и читает данные о задачах/чек-листах" "SQL"
            people_prediction -> database "Чтение обучающих данных и логов" "SQL"
            mobile_app -> database "Запись/чтение данных пользователей и событий" "SQL"
        }

        user -> mobile_app "Использует приложение"
        admin -> database "Обслуживает и проверяет данные"
    }

    views {
        systemContext system "C1_Context" {
            include *
            autolayout lr
        }

        container system "C2_Containers" {
            include *
            autolayout lr
        }

        component system.helper_bot "C4_HelperBot_Components" {
            include *
            autolayout lr
        }

        component system.people_prediction "C4_PredictionService_Components" {
            include *
            autolayout lr
        }

        dynamic system "GenerateChecklistAndNotify" {
            user -> mobile_app "Создание мероприятия"
            mobile_app -> helper_bot "POST /schedule_event"
            helper_bot -> "OpenAI API" "Получение чек-листа"
            helper_bot -> database "Сохранение задач"
            helper_bot -> "Firebase FCM" "Отправка уведомлений"
        }

        dynamic system "PredictParticipation" {
            user -> mobile_app "Просматривает мероприятие"
            mobile_app -> people_prediction "Запрос на прогноз"
            people_prediction -> database "Чтение пользовательских ивентов"
            people_prediction -> people_prediction.PredictionModule "Инференс модели"
        }
    }
}
