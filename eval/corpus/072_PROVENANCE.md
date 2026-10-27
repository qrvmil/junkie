# Происхождение записи EuRoC MH01

Исходные данные: **EuRoC MAV, Machine Hall 01 easy**, Michael Burri, Janosch Nikolic и соавторы, ETH Zürich. Датасет: https://doi.org/10.3929/ethz-b-000690084 . Публикация: *The EuRoC micro aerial vehicle datasets*, IJRR, 2016, https://doi.org/10.1177/0278364915620033 . Актуальная страница: https://projects.asl.ethz.ch/datasets/euroc-mav/ .

Референс занятия: https://foxglove.dev/blog/converting-euroc-mav-dataset-to-mcap и https://github.com/foxglove/tutorials/tree/main/datasets/EuRoC_MAV . В статье используются камеры и IMU EuRoC и отдельный запуск RTAB-Map. Наш комплект содержит исходные данные того же MH01, перепакованные отдельно; это **не готовая запись результата RTAB-Map из статьи**.

Для загрузки использовано публичное зеркало уже преобразованных MCAP: https://huggingface.co/datasets/gpdaniels/slam-datasets , файл `euroc-mav/mh_01_easy.mcap`, ревизия `0aa4102e426c0f12c9dcefb772579199cc30c8e2` (из HTTP-заголовка ответа при подготовке). Оно сохраняет данные в ROS 2 CDR со схемами внутри файла и приводит пространственные данные к общей системе координат. Источник зеркала и точные байты/контрольная сумма учебного фрагмента указаны в manifest.json.

Преобразования для семинара: выбран интервал 35–55 с от начала записи, изображения обеих камер прорежены с 20 до 5 кадров/с, сообщения IMU, CameraInfo и TF сохранены в этом интервале, временные метки и координатные соглашения зеркала сохранены. Запись сжата Zstandard. Числа исходных сообщений не синтезированы.

Мировой frame — `root`, корпус — `ego`, frames сенсоров — `sensor/image_01`, `sensor/image_02`, `sensor/imu_01`. Движение root → ego — **ground truth датасета**; отношения ego → сенсоры описывают калиброванное крепление. Это не результат SLAM, запущенного при подготовке занятия. Мы не добавляли облако точек и не выдаём изображение за карту.

ETH Research Collection указывает правовой статус **In Copyright – Non-Commercial Use Permitted**. Источник и авторство сохранены; комплект подготовлен для некоммерческого учебного использования. У зеркала лицензия отмечена unknown, поэтому ему не приписывается отдельное разрешение и данные не перелицензируются как MIT. Страница правового статуса: https://www.research-collection.ethz.ch/items/bcaf173e-5dac-484b-bc37-faf97a594f1f . Исходный код собственной учебной модели и инструментов отделён от прав на данные.

Готовый учебный файл: [скачать MCAP](https://example.invalid/course/mcap-download (GitLab курса, требуется вход). Сохраните его как `data/euroc-mh01.mcap`. В Git хранятся только эта справка и manifest.json, а сама запись — в Package Registry.
