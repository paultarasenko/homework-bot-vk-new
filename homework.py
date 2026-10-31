import logging
import os
import sys
import time

import requests
import vk_api
from dotenv import load_dotenv
from vk_api.utils import get_random_id

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
VK_TOKEN = os.getenv('VK_TOKEN')
VK_USER_ID = os.getenv('VK_USER_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет доступность обязательных переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'VK_TOKEN': VK_TOKEN,
        'VK_USER_ID': VK_USER_ID,
    }
    missing = [name for name, value in tokens.items() if not value]
    for name in missing:
        logger.critical(
            f'Отсутствует обязательная переменная окружения: {name!r}'
        )
    return not missing


def send_message(vk, message):
    """Отправляет сообщение в VK. Возвращает True при успехе."""
    try:
        vk.messages.send(
            user_id=VK_USER_ID,
            message=message,
            random_id=get_random_id(),
        )
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в VK: {error}')
        return False
    logger.debug(f'Бот отправил сообщение "{message}"')
    return True


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ в виде словаря."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise ConnectionError(
            f'Эндпоинт {ENDPOINT} недоступен: {error}'
        )
    if response.status_code != 200:
        raise ConnectionError(
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}'
        )
    return response.json()


def check_response(response):
    """Проверяет ответ API и возвращает список домашних работ."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API должен быть словарём, получен {type(response)}'
        )
    for key in ('homeworks', 'current_date'):
        if key not in response:
            raise KeyError(f'В ответе API нет ключа {key!r}')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            f'Ключ homeworks должен содержать список, '
            f'получен {type(homeworks)}'
        )
    return homeworks


def parse_status(homework):
    """Возвращает сообщение о статусе конкретной домашней работы."""
    if not isinstance(homework, dict):
        raise TypeError(
            f'Домашняя работа должна быть словарём, получен {type(homework)}'
        )
    for key in ('homework_name', 'status'):
        if key not in homework:
            raise KeyError(f'В данных о домашней работе нет ключа {key!r}')

    homework_name = homework['homework_name']

    status = homework['status']

    if status not in HOMEWORK_VERDICTS:

        raise ValueError(f'Неожиданный статус домашней работы: {status}')

    verdict = HOMEWORK_VERDICTS[status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():

        sys.exit('Программа принудительно остановлена.')

    # Создаем сессию для бота

    vk_session = vk_api.VkApi(token=VK_TOKEN)

    vk = vk_session.get_api()

    timestamp = int(time.time())

    last_error = ''

    while True:

        try:

            response = get_api_answer(timestamp)

            homeworks = check_response(response)

            if homeworks:

                message = parse_status(homeworks[0])

                if send_message(vk, message):

                    timestamp = response.get('current_date', timestamp)

            else:

                logger.debug('В ответе нет новых статусов.')

            last_error = ''

        except Exception as error:

            message = f'Сбой в работе программы: {error}'

            logger.error(message)

            if message != last_error and send_message(vk, message):

                last_error = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':

    main()
