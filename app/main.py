import base64
from threading import Lock
from datetime import datetime, timedelta

import boto3
import requests
from botocore.exceptions import ClientError
from flask import Flask, abort, jsonify, request
from flask_cors import CORS
from flask_marshmallow import Marshmallow
from pennsieve import Pennsieve
# from app.config import Config
from app.mapstate import MapState
from pennsieve.base import UnauthorizedException as PSUnauthorizedException

from app.config import Config
from app.serializer import ContactRequestSchema

from scripts.email_sender import EmailSender
from app.process_kb_results import *
from requests.auth import HTTPBasicAuth
import os


app = Flask(__name__)
# set environment variable
app.config["ENV"] = Config.DEPLOY_ENV

CORS(app)

ma = Marshmallow(app)
email_sender = EmailSender()
mongo = None
ps = None
s3 = boto3.client(
    "s3",
    aws_access_key_id=Config.SPARC_PORTAL_AWS_KEY,
    aws_secret_access_key=Config.SPARC_PORTAL_AWS_SECRET,
    region_name="us-east-1",
)

os.environ["AWS_ACCESS_KEY_ID"] = Config.SPARC_PORTAL_AWS_KEY
os.environ["AWS_SECRET_ACCESS_KEY"] = Config.SPARC_PORTAL_AWS_SECRET

biolucida_lock = Lock()

try:
  mapstate = MapState(Config.DATABASE_URL)
except:
  mapstate = None

class Biolucida(object):
    _token = ''
    _expiry_date = datetime.now() + timedelta(999999)
    _pending_authentication = False

    @staticmethod
    def set_token(value):
        Biolucida._token = value

    def token(self):
        return self._token

    @staticmethod
    def set_expiry_date(value):
        Biolucida._expiry_date = value

    def expiry_date(self):
        return self._expiry_date

    @staticmethod
    def set_pending_authentication(value):
        Biolucida._pending_authentication = value

    def pending_authentication(self):
        return self._pending_authentication


@app.errorhandler(404)
def resource_not_found(e):
    return jsonify(error=str(e)), 404


@app.before_first_request
def connect_to_pennsieve():
    global ps
    try:
        ps = Pennsieve(
            api_token=Config.PENNSIEVE_API_TOKEN,
            api_secret=Config.PENNSIEVE_API_SECRET,
            env_override=False,
            host=Config.PENNSIEVE_API_HOST
        )
    except requests.exceptions.HTTPError as err:
        logging.error("Unable to connect to Pennsieve host")
        logging.error(err)
    except PSUnauthorizedException as err:
        logging.error("Unable to authorise with Pennsieve Api")
        logging.error(err)
    except Exception as err:
        logging.error("Unknown Error")
        logging.error(err)


# @app.before_first_request
# def connect_to_mongodb():
#     global mongo
#     mongo = MongoClient(Config.MONGODB_URI)


@app.route("/health")
def health():
    return json.dumps({"status": "healthy"})


@app.route("/contact", methods=["POST"])
def contact():
    data = json.loads(request.data)
    contact_request = ContactRequestSchema().load(data)

    name = contact_request["name"]
    email = contact_request["email"]
    message = contact_request["message"]

    email_sender.send_email(name, email, message)

    return json.dumps({"status": "sent"})


# Returns a list of embargoed (unpublished) datasets
# @api_blueprint.route('/datasets/embargo')
# def embargo():
#     collection = mongo[Config.MONGODB_NAME][Config.MONGODB_COLLECTION]
#     embargo_list = list(collection.find({}, {'_id':0}))
#     return json.dumps(embargo_list)


# Download a file from S3
@app.route("/download")
def create_presigned_url(expiration=3600):
    bucket_name = "pennsieve-prod-discover-publish-use1"
    key = request.args.get("key")
    contentType = request.args.get("contentType") or "application/octet-stream"
    response = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": key, "RequestPayer": "requester", "ResponseContentType": contentType},
        ExpiresIn=expiration,
    )

    return response


# Reverse proxy for objects from S3, a simple get object
# operation. This is used by scaffoldvuer and it's
# important to keep the relative <path> for accessing
# other required files.
@app.route("/s3-resource/<path:path>")
def direct_download_url(path):
    bucket_name = "pennsieve-prod-discover-publish-use1"

    head_response = s3.head_object(
        Bucket=bucket_name,
        Key=path,
        RequestPayer="requester"
    )

    content_length = head_response.get('ContentLength', None)
    if content_length and content_length > 20971520:  # 20 MB
        return abort(413, description=f"File too big to download: {content_length}")

    response = s3.get_object(
        Bucket=bucket_name,
        Key=path,
        RequestPayer="requester"
    )
    resource = response["Body"].read()
    return resource


@app.route("/sim/dataset/<id_>")
def sim_dataset(id_):
    if request.method == "GET":
        req = requests.get("{}/datasets/{}".format(Config.DISCOVER_API_HOST, id_))
        json_response = req.json()
        inject_markdown(json_response)
        inject_template_data(json_response)
        return jsonify(json_response)


@app.route("/search_dataset_by_mime_type/")
def search_datasets():
    mime_type = request.args.getlist('mime_type')[0]


@app.route("/dataset_info_from_doi/")
def get_dataset_info():
    doi = request.args.getlist('doi')[0]
    query = {
        "match": {
            "item.curie": {
                "query": f"DOI:{doi}",
                "operator": "and"
            }
        }
    }
    # query = {
    #             "match": {
    #                 "item.identifier": {
    #                     "query": f"{identifier}",
    #                     "operator": "and"
    #                 }
    #             }
    #         }

    return dataset_search(query)


def dataset_search(query):
    try:
        payload = {
            "query": query
        }
        params = {
            "api_key": Config.KNOWLEDGEBASE_KEY
        }
        response = requests.post(f'{Config.SCI_CRUNCH_HOST}/_search',
                                 json=payload, params=params)

        return process_kb_results(response.json())
    except requests.exceptions.HTTPError as err:
        logging.error(err)

        return jsonify({'error': err})


# /search/: Returns sci-crunch results for a given <search> query
@app.route("/search/", defaults={'query': ''})
@app.route("/search/<query>")
def kb_search(query):
    try:
        response = requests.get(f'{Config.SCI_CRUNCH_HOST}/_search?q={query}&api_key={Config.KNOWLEDGEBASE_KEY}')
        return process_kb_results(response.json())
    except requests.exceptions.HTTPError as err:
        logging.error(err)
        return json.dumps({'error': err})


# /filter-search/: Returns sci-crunch results with optional params for facet filtering, sizing, and pagination
@app.route("/filter-search/", defaults={'query': ''})
@app.route("/filter-search/<query>/")
def filter_search(query):
    terms = request.args.getlist('term')
    facets = request.args.getlist('facet')
    size = request.args.get('size')
    start = request.args.get('start')

    # Create request
    data = create_filter_request(query, terms, facets, size, start)

    # Send request to sci-crunch
    try:
        response = requests.post(
            f'{Config.SCI_CRUNCH_HOST}/_search?api_key={Config.KNOWLEDGEBASE_KEY}',
            json=data)
        results = process_kb_results(response.json())
    except requests.exceptions.HTTPError as err:
        logging.error(err)
        return jsonify({'error': str(err), 'message': 'Sci-crunch is not currently reachable, please try again later'}), 502
    except json.JSONDecodeError:
        return jsonify({'message': 'Could not parse Sci-crunch output, please try again later',
                        'error': 'JSONDecodeError'}), 502
    return results


# /get-facets/: Returns available sci-crunch facets for filtering over given a <type> ('species', 'gender' etc)
@app.route("/get-facets/<type_>")
def get_facets(type_):
    # Create facet query
    type_map, data = create_facet_query(type_)

    # Make a request for each sci-crunch parameter
    results = []
    for path in type_map[type_]:
        data['aggregations'][f'{type_}']['terms']['field'] = path
        response = requests.post(
            f'{Config.SCI_CRUNCH_HOST}/_search?api_key={Config.KNOWLEDGEBASE_KEY}',
            json=data)
        try:
            json_result = response.json()
            results.append(json_result)
        except json.JSONDecodeError:
            return jsonify({'message': 'Could not parse Sci-crunch output, please try again later',
                            'error': 'JSONDecodeError'}), 502

    # Select terms from the results
    terms = []
    for result in results:
        terms += result['aggregations'][f'{type_}']['buckets']

    return jsonify(terms)


def inject_markdown(resp):
    if "readme" in resp:
        mark_req = requests.get(resp.get("readme"))
        resp["markdown"] = mark_req.text


def inject_template_data(resp):
    id_ = resp.get("id")
    version = resp.get("version")
    if id_ is None or version is None:
        return

    try:
        response = s3.get_object(
            Bucket="pennsieve-prod-discover-publish-use1",
            Key="{}/{}/files/template.json".format(id, version),
            RequestPayer="requester",
        )
    except ClientError:
        # If the file is not under folder 'files', check under folder 'packages'
        logging.warning(
            "Required file template.json was not found under /files folder, trying under /packages..."
        )
        try:
            response = s3.get_object(
                Bucket="pennsieve-prod-discover-publish-use1",
                Key="{}/{}/packages/template.json".format(id, version),
                RequestPayer="requester",
            )
        except ClientError as e:
            logging.error(e)
            return

    template = response["Body"].read()

    try:
        template_json = json.loads(template)
    except ValueError as e:
        logging.error(e)
        return

    resp["study"] = {
        "uuid": template_json.get("uuid"),
        "name": template_json.get("name"),
        "description": template_json.get("description"),
    }


@app.route("/project/<project_id>", methods=["GET"])
def datasets_by_project_id(project_id):
    # 1 - call discover to get awards on all datasets (let put a very high limit to make sure we do not miss any)

    req = requests.get(
        "{}/search/records?limit=1000&offset=0&model=award".format(
            Config.DISCOVER_API_HOST
        )
    )

    records = req.json()["records"]

    # 2 - filter response to retain only awards with project_id
    result = filter(lambda x: "award_id" in x["properties"] and x["properties"]["award_id"] == project_id, records)

    ids = map(lambda x: str(x["datasetId"]), result)

    separator = "&ids="

    list_ids = separator.join(ids)

    # 3 - get the datasets from the list of ids from #2

    if len(list_ids) > 0:
        return requests.get(
            "{}/datasets?ids={}".format(Config.DISCOVER_API_HOST, list_ids)
        ).json()
    else:
        abort(404, description="Resource not found")


@app.route("/get_owner_email/<int:owner_id>", methods=["GET"])
def get_owner_email(owner_id):
    # Filter to find user based on provided int id
    org = ps._api._organization
    members = ps._api.organizations.get_members(org)
    res = [x for x in members if x.int_id == owner_id]

    if not res:
        abort(404, description="Owner not found")
    else:
        return jsonify({"email": res[0].email})


@app.route("/file/", methods=["GET"])
def fetch_file_from_s3():
    # print(request.args)
    doi = request.args.getlist('doi')
    filepath = request.args.getlist('filepath')
    print(doi, filepath)
    # size = request.args.get('size')
    # start = request.args.get('start')
    abort(404, description="Not implemented")


@app.route("/data_location/", methods=["GET"])
def data_location_via_discover():
    doi = request.args.getlist('doi')
    print(doi)
    print(bf)
    print(dir(bf))
    print(bf.datasets)
    print(bf.get_dataset('10.26275', 'dwly-naxx'))
    abort(404, description="Not implemented")


@app.route("/thumbnail/<image_id>", methods=["GET"])
def thumbnail_by_image_id(image_id, recursive_call=False):
    bl = Biolucida()

    with biolucida_lock:
        if not bl.token():
            authenticate_biolucida()

    url = Config.BIOLUCIDA_ENDPOINT + "/thumbnail/{0}".format(image_id)
    headers = {
        'token': bl.token(),
    }

    response = requests.request("GET", url, headers=headers)
    encoded_content = base64.b64encode(response.content)
    # Response from this endpoint is binary on success so the easiest thing to do is
    # check for an error response in encoded form.
    if encoded_content == b'eyJzdGF0dXMiOiJBZG1pbiB1c2VyIGF1dGhlbnRpY2F0aW9uIHJlcXVpcmVkIHRvIHZpZXcvZWRpdCB1c2VyIGluZm8uIFlvdSBtYXkgbmVlZCB0byBsb2cgb3V0IGFuZCBsb2cgYmFjayBpbiB0byByZXZlcmlmeSB5b3VyIGNyZWRlbnRpYWxzLiJ9' \
            and not recursive_call:
        # Authentication failure, try again after resetting token.
        with biolucida_lock:
            bl.set_token('')

        encoded_content = thumbnail_by_image_id(image_id, True)

    return encoded_content


@app.route("/image/<image_id>", methods=["GET"])
def image_info_by_image_id(image_id):
    url = Config.BIOLUCIDA_ENDPOINT + "/image/{0}".format(image_id)
    response = requests.request("GET", url)
    return response.json()


@app.route("/image_search/<dataset_id>", methods=["GET"])
def image_search_by_dataset_id(dataset_id):
    url = Config.BIOLUCIDA_ENDPOINT + "/imagemap/search_dataset/discover/{0}".format(dataset_id)
    response = requests.request("GET", url)
    return response.json()


def authenticate_biolucida():
    bl = Biolucida()
    url = Config.BIOLUCIDA_ENDPOINT + "/authenticate"

    payload = {'username': Config.BIOLUCIDA_USERNAME,
               'password': Config.BIOLUCIDA_PASSWORD,
               'token': ''}
    files = [
    ]
    headers = {}

    response = requests.request("POST", url, headers=headers, data=payload, files=files)
    if response.status_code == requests.codes.ok:
        content = response.json()
        bl.set_token(content['token'])


#get the share link for the current map content
@app.route("/map/getshareid", methods=["POST"])
def get_share_link():
    #Do not commit to database when testing
    commit = True
    if app.config["TESTING"]:
        commit = False
    if mapstate:
        json_data = request.get_json()
        if json_data and 'state' in json_data:
            state = json_data['state']
            uuid = mapstate.pushState(state, commit)
            return jsonify({"uuid": uuid})
        abort(400, description="State not specified")
    else:
        abort(404, description="Database not available")


#get the map state using the share link id
@app.route("/map/getstate", methods=["POST"])
def get_map_state():
    if mapstate:
        json_data = request.get_json()
        if json_data and 'uuid' in json_data:
            uuid = json_data['uuid']
            state = mapstate.pullState(uuid)
            if state:
                return jsonify({"state": mapstate.pullState(uuid)})
        abort(400, description="Key missing or did not find a match")
    else:
        abort(404, description="Database not available")

@app.route("/tasks", methods=["POST"])
def create_wrike_task():
    json_data = request.get_json()
    if json_data and 'title' in json_data and 'description' in json_data :
        title = json_data["title"]
        description = json_data["description"]
        hed = {'Authorization': 'Bearer ' + Config.WRIKE_TOKEN}
        url = 'https://www.wrike.com/api/v4/folders/IEADBYQEI4MM37FH/tasks'

        data = {
            "title": title,
            "description": description,
            "customStatus": "IEADBYQEJMBJODZU",
            "followers": [Config.CCB_HEAD_WRIKE_ID,Config.DAT_CORE_TECH_LEAD_WRIKE_ID,Config.MAP_CORE_TECH_LEAD_WRIKE_ID,Config.K_CORE_TECH_LEAD_WRIKE_ID,Config.SIM_CORE_TECH_LEAD_WRIKE_ID,Config.MODERATOR_WRIKE_ID],
            "responsibles": [Config.CCB_HEAD_WRIKE_ID,Config.DAT_CORE_TECH_LEAD_WRIKE_ID,Config.MAP_CORE_TECH_LEAD_WRIKE_ID,Config.K_CORE_TECH_LEAD_WRIKE_ID,Config.SIM_CORE_TECH_LEAD_WRIKE_ID,Config.MODERATOR_WRIKE_ID],
            "follow":False,
            "dates":{"type":"Backlog"}
        }

        resp = requests.post(
            url=url,
            json=data,
            headers=hed
        )

        if resp.status_code == 200:
            return jsonify(
                title=title,
                description=description,
                task_id=resp.json()["data"][0]["id"]
            )
        else:
            return resp.json()
    else:
        abort(400, description="Missing title or description")

@app.route("/mailchimp", methods=["POST"])
def subscribe_to_mailchimp():
    json_data = request.get_json()
    if json_data and 'email_address' in json_data and 'first_name' in json_data and 'last_name' in json_data:
        email_address = json_data["email_address"]
        first_name = json_data['first_name']
        last_name = json_data['last_name']
        auth=HTTPBasicAuth('AnyUser', Config.MAILCHIMP_API_KEY)
        url = 'https://us2.api.mailchimp.com/3.0/lists/c81a347bd8/members'

        data = {
            "email_address": email_address,
            "status": "subscribed",
            "merge_fields" : {
                "FNAME": first_name,
                "LNAME": last_name
            }
        }
        resp = requests.post(
            url=url,
            json=data,
            auth=auth
        )

        if resp.status_code == 200:
            return jsonify(
                email_address=email_address,
                id=resp.json()["id"]
            )
        else:
            return resp.json()
    else:
        abort(400, description="Missing email_address, first_name or last_name")
