class PIDConfigException(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)

class APIError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)