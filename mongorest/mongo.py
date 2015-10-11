from json import JSONDecodeError
from flask import Blueprint, current_app, g, request, abort
from flask.views import MethodView
from pymongo import uri_parser, MongoClient
from pymongo.errors import OperationFailure
from werkzeug.local import LocalProxy
from bson import json_util, ObjectId
from bson.errors import InvalidId
from werkzeug.routing import BaseConverter


mongo = Blueprint('mongo', __name__, url_prefix='/<collection>')


def to_json(data):
    indent = None
    separators = (',', ':')
    if not request.is_xhr:
        indent = 2
        separators = (', ', ': ')
    return current_app.response_class(
        (json_util.dumps(data, indent=indent, separators=separators), '\n'),
        mimetype='application/json')


def from_json(content):
    try:
        return json_util.loads(content)
    except JSONDecodeError:
        abort(400)


class ApiError(Exception):
    status_code = 400

    def __init__(self, message, payload=None, exception=None, status_code=None):
        Exception.__init__(self)
        self.message = message
        self.exception = exception
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def as_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        try:
            rv['exception'] = self.exception.details
        except AttributeError:
            rv['exception'] = str(self.exception)
        return rv


@mongo.errorhandler(ApiError)
def errorhandler(e):
    return to_json(e.as_dict()), e.status_code


@mongo.url_value_preprocessor
def pull_collection(endpoint, values):
    c = values.pop('collection')
    if c not in current_app.config.get('MONGO_COLLECTIONS'):
        raise ApiError('Not found', status_code=404)
    g.collection = c


class MongoView(MethodView):
    def get(self, object_id):
        if object_id is None:
            return self.find()
        return self.find_one(object_id)

    def find_one(self, object_id):
        collection = db[g.collection]
        item = collection.find_one(object_id)
        if not item:
            raise ApiError('Not found', status_code=404)
        return to_json(item)

    def find(self):
        collection = db[g.collection]
        limit = int(request.args.get('limit', 0))
        skip = int(request.args.get('skip', 0))
        query = request.args.get('query')
        projection = request.args.get('projection')
        if query:
            query = from_json(query)
        if projection:
            projection = from_json(projection)
        result = collection.find(query, projection).limit(limit).skip(skip)
        return to_json(result)

    def url(self, object_id):
        return '{}://{}/{}/{}'.format(request.scheme, request.host, g.collection, object_id)

    def post(self):
        data = from_json(request.data.decode(request.charset))
        collection = db[g.collection]
        try:
            result = collection.insert_one(data)
        except OperationFailure as e:
            raise ApiError('Bad request', payload=data, exception=e, status_code=400)
        url = self.url(str(result.inserted_id))
        return to_json(dict(result=url)), 201

    def put(self, object_id):
        collection = db[g.collection]
        data = from_json(request.data.decode(request.charset))
        try:
            result = collection.update_one({'_id': object_id}, data)
        except OperationFailure as e:
            raise ApiError('Bad request', payload=data, exception=e, status_code=400)
        return to_json(dict(acknowledged=result.acknowledged))

    def delete(self, object_id):
        collection = db[g.collection]
        collection.delete_one({'_id': object_id})
        return '', 204


class OidConverter(BaseConverter):
    def to_python(self, value):
        try:
            return ObjectId(value)
        except InvalidId:
            raise abort(400)

    def to_url(self, value):
        return str(value)


mongo_view = MongoView.as_view('mongo_view')
mongo.add_url_rule('/', defaults={'object_id': None}, view_func=mongo_view, methods=['GET'])
mongo.add_url_rule('/', view_func=mongo_view, methods=['POST'])
mongo.add_url_rule('/<oid:object_id>', view_func=mongo_view, methods=['GET', 'PUT', 'DELETE'])


def get_mongodb():
    db_inst = getattr(g, 'mongodb', None)
    if not db_inst:
        mongo_uri = current_app.config.get('MONGO_URI', None)
        parsed = uri_parser.parse_uri(mongo_uri)
        db_inst = g.mongodb = MongoClient(mongo_uri)[parsed.get('database')]
    return db_inst


db = LocalProxy(get_mongodb)
