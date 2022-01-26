import requests.auth


class LessonlyClient:
    _base_url_v1 = 'https://api.lessonly.com/api/v1'
    _base_url_v1_1 = 'https://api.lessonly.com/api/v1.1'

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = requests.auth.HTTPBasicAuth(self.username, self.password)

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
