import datetime
import logging
import requests.auth

log = logging.getLogger(__name__)

class LessonlyClient:
    _base_url_v1 = 'https://api.lessonly.com/api/v1'
    _base_url_v1_1 = 'https://api.lessonly.com/api/v1.1'

    def __init__(self, username: str, password: str):
        self.assignments_updated_at_filter = datetime.date(2000, 1, 1)
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = requests.auth.HTTPBasicAuth(self.username, self.password)

    @property
    def assignments(self) -> list[dict]:
        url = f'{self._base_url_v1_1}/assignments'
        params = {
            'gt[updated_at]': str(self.assignments_updated_at_filter),
            'page': 1,
            'per_page': 200,
        }
        while True:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            yield from data.get('assignments')

            current_page = params.get('page')
            total_pages = data.get('total_pages')
            log.debug(f'Done getting assignments on page {current_page} of {total_pages}')
            if current_page < total_pages:
                params.update({
                    'page': params.get('page') + 1
                })
            else:
                break

    def get_lesson(self, lesson_id: int) -> dict:
        response = self.session.get(f'{self._base_url_v1_1}/lessons/{lesson_id}')
        response.raise_for_status()
        data = response.json()
        return data

    def get_path(self, path_id: int) -> dict:
        response = self.session.get(f'{self._base_url_v1}/paths/{path_id}')
        response.raise_for_status()
        data = response.json()
        return data

    @property
    def lessons(self) -> list[dict]:
        response = self.session.get(f'{self._base_url_v1_1}/lessons')
        response.raise_for_status()
        data = response.json()
        return data.get('lessons')

    @property
    def paths(self) -> list[dict]:
        response = self.session.get(f'{self._base_url_v1_1}/paths')
        response.raise_for_status()
        data = response.json()
        return data.get('paths')

    @property
    def users(self) -> list[dict]:
        url = f'{self._base_url_v1_1}/users'
        params = {
            'page': 1
        }
        while True:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            yield from data.get('users')
            if params.get('page') < data.get('total_pages'):
                params.update({
                    'page': params.get('page') + 1
                })
            else:
                break
