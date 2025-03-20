from pathlib import Path

from cincoconfig import (
    ApplicationModeField,
    BoolField,
    Config,
    IPv4AddressField,
    NumberField,
    PortField,
    Schema,
    SecureField,
    StringField,
    UrlField,
)

# first, define the configuration's schema -- the fields available that
# customize the application's or library's behavior
schema = Schema(env=True)
schema.mode = ApplicationModeField(default="dev", modes=["dev", "prod"])
schema.port = PortField(default=1337, required=True)
schema.address = IPv4AddressField(default="0.0.0.0", required=True)

# openapi options
schema.openapi.name = StringField(default="ApiSec Vulnerable REST API", required=True)
schema.openapi.description = StringField(default="ApiSec Vulnerable REST API", required=True)
schema.openapi.openapi_url = StringField(default=None, regex=r"\/[a-zA-Z0-9\/]+")
schema.openapi.docs_url = StringField(default=None, regex=r"\/[a-zA-Z0-9\/]+")
schema.openapi.redocs_url = StringField(default=None, regex=r"\/[a-zA-Z0-9\/]+")
schema.openapi.show_scopes = BoolField(default=True)
schema.openapi.server = StringField()

schema.log.level = StringField(
    default="info",
    transform_case="upper",
    choices=["CRITICAL", "FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "NOTSET"],
)
schema.log.stream = StringField(default="stdout", choices=["stdout", "stderr"])
schema.log.format = StringField(default="text", choices=["text", "json"])
schema.log.sql = BoolField(default=False, help="echo SQL queries to log")
# schema.log.format = StringField(
#     default='%(levelprefix)s %(asctime)s %(client_addr)s - "%(request_line)s" %(status_code)s'
# )

schema.auth.token_url = StringField(required=True)
schema.auth.jwt.secret_key = SecureField(required=True)
schema.auth.jwt.expiration = NumberField(
    required=True, default=10800, description="Seconds a JWT is valid for", type_cls=int
)
schema.auth.jwt.algorithm = StringField(
    required=True,
    default="HS256",
    choices=[
        "HS256",
        "HS384",
        "HS512",
        "ES256",
        "ES256K",
        "ES384",
        "ES512",
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "EdDSA",
    ],
)

schema.db.url = UrlField()

config = schema()


def load_config_file(conf: Config, filepath: Path = None) -> Config:
    filepath = filepath or Path(__file__).parent / "config.yaml"
    filepath.resolve()
    if filepath.is_file():
        conf.load(str(filepath), format="yaml")
    return conf


if __name__ == "__main__":
    load_config_file(config)
    config.validate()
    print(config.dumps(format="json", pretty=True, sensitive_mask=None).decode())
