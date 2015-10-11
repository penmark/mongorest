from bson import json_util, ObjectId
from flask import Blueprint, current_app, g, request, abort
from flask.views import MethodView
from pymongo import uri_parser, MongoClient
from werkzeug.local import LocalProxy
from bson import json_util, ObjectId
from bson.errors import InvalidId
from werkzeug.routing import BaseConverter


mongo = Blueprint('mongo', __name__, url_prefix='/<collection>')


def jsonify(data):
    indent = None
    separators = (',', ':')
    if not request.is_xhr:
        indent = 2
        separators = (', ', ': ')
    return current_app.response_class(
        (json_util.dumps(data, indent=indent, separators=separators), '\n'),
        mimetype='application/json')


@mongo.errorhandler(404)
def errorhandler(e):
    return jsonify(dict(error=e.name)), e.code


@mongo.url_value_preprocessor
def pull_collection(endpoint, values):
    c = values.pop('collection')
    if c not in current_app.config.get('MONGO_COLLECTIONS'):
        abort(404)
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
            abort(404)
        return jsonify(item)

    def find(self):
        collection = db[g.collection]
        limit = int(request.args.get('limit', 0))
        skip = int(request.args.get('skip', 0))
        query = request.args.get('query')
        projection = request.args.get('projection')
        if query:
            query = json_util.loads(query)
        if projection:
            projection = json_util.loads(projection)
        result = collection.find(query, projection).limit(limit).skip(skip)
        return jsonify(result)

    def url(self, object_id):
        return '{}://{}/{}/{}'.format(request.scheme, request.host, g.collection, object_id)

    def post(self):
        data = json_util.loads(request.data.decode(request.charset))
        collection = db[g.collection]
        result = collection.insert_one(data)
        url = self.url(str(result.inserted_id))
        return jsonify(dict(result=url)), 201

    def put(self, object_id):
        collection = db[g.collection]
        data = json_util.loads(request.data.decode(request.charset))
        result = collection.update_one({'_id': object_id}, data)
        return jsonify(dict(acknowledged=result.acknowledged))

    def delete(self, object_id):
        collection = db[g.collection]
        collection.delete_one({'_id': ObjectId(object_id)})
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
