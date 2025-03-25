from datetime import datetime


class PIDConfigException(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)


class APIError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class OutdatedError(APIError):
    def __init__(self, outdated_datetime: datetime):
        message = f'Outdated since {outdated_datetime}, for {datetime.now() - outdated_datetime}'
        super().__init__(message, status_code=500)
