from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    bot_token: str
    bot_username: str = ""
    public_url: str = ""
    mini_app_url: str = ""
    jwt_secret: str = "change-me"
    cors_origin: str = "*"
    premium_price_stars: int = 250
    groq_api_key: str = ""
    premium_group_id: int = 0

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origin.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
