import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    PORTAL_API_HOST = os.environ.get("PORTAL_API_HOST", "http://localhost:4000")
    PENNSIEVE_API_HOST = os.environ.get("PENNSIEVE_API_HOST")
    PENNSIEVE_API_SECRET = os.environ.get("PENNSIEVE_API_SECRET", "local-secret-key")
    PENNSIEVE_API_TOKEN = os.environ.get("PENNSIEVE_API_TOKEN", "local-api-key")
    PENNSIEVE_EMBARGO_TEAM_ID = os.environ.get("PENNSIEVE_EMBARGO_TEAM_ID")
    DATABASE_URL = os.environ.get('DATABASE_URL')
    DISCOVER_API_HOST = os.environ.get(
        "DISCOVER_API_HOST", "https://api.pennsieve.io/discover"
    )
    GRAPHENEDB_BOLT_PASSWORD = os.environ.get("GRAPHENEDB_BOLT_PASSWORD")
    GRAPHENEDB_BOLT_URL = os.environ.get("GRAPHENEDB_BOLT_URL")
    GRAPHENEDB_BOLT_USER = os.environ.get("GRAPHENEDB_BOLT_USER")
    MONGODB_COLLECTION = os.environ.get("MONGODB_COLLECTION")
    MONGODB_NAME = os.environ.get("MONGODB_NAME")
    MONGODB_URI = os.environ.get("MONGODB_URI")
    SES_ARN = os.environ.get("SES_ARN")
    SES_SENDER = os.environ.get("SES_SENDER")
    SPARC_PORTAL_AWS_KEY = os.environ.get("SPARC_PORTAL_USER_ID")
    SPARC_PORTAL_AWS_SECRET = os.environ.get("SPARC_PORTAL_USER_SECRET")
    OSPARC_HOST = os.environ.get("OSPARC_HOST", "https://osparc.io")
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    BIOLUCIDA_ENDPOINT = os.environ.get("BIOLUCIDA_ENDPOINT", "https://sparc.biolucida.net/api/v1")
    BIOLUCIDA_USERNAME = os.environ.get("BIOLUCIDA_USERNAME", "major-user")
    BIOLUCIDA_PASSWORD = os.environ.get("BIOLUCIDA_PASSWORD", "local-password")
    KNOWLEDGEBASE_KEY = os.environ.get("KNOWLEDGEBASE_KEY", "secret-key")
    DEPLOY_ENV = os.environ.get("DEPLOY_ENV", "development")
    SPARC_APP_HOST = os.environ.get("SPARC_APP_HOST", "https://sparc-app.herokuapp.com")
    SCI_CRUNCH_HOST = os.environ.get("SCICRUNCH_HOST", "https://scicrunch.org/api/1/elastic/SPARC_Datasets_pr")
    MAPSTATE_TABLENAME = os.environ.get("MAPSTATE_TABLENAME", "mapstates")
    WRIKE_TOKEN = os.environ.get("WRIKE_TOKEN")
    SIM_CORE_TECH_LEAD_WRIKE_ID = os.environ.get("SIM_CORE_TECH_LEAD_WRIKE_ID")
    MAP_CORE_TECH_LEAD_WRIKE_ID = os.environ.get("MAP_CORE_TECH_LEAD_WRIKE_ID")
    DAT_CORE_TECH_LEAD_WRIKE_ID = os.environ.get("DAT_CORE_TECH_LEAD_WRIKE_ID")
    K_CORE_TECH_LEAD_WRIKE_ID = os.environ.get("K_CORE_TECH_LEAD_WRIKE_ID")
    CCB_HEAD_WRIKE_ID = os.environ.get("CCB_HEAD_WRIKE_ID")
    MODERATOR_WRIKE_ID = os.environ.get("MODERATOR_WRIKE_ID")
    MAILCHIMP_API_KEY = os.environ.get("MAILCHIMP_API_KEY")

