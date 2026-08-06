from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    bot_token: str
    database_url: str
    jwt_secret: str
    public_url: str = ""
    mini_app_url: str = ""
    bot_username: str = ""
    cors_origins: str = "*"

    model_config = {"env_file": ".env"}

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

settings = Settings()
