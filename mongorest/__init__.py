from flask import Flask


class DefaultSettings(object):
    MONGO_URI = 'mongodb://localhost/media'
    MONGO_COLLECTIONS = ['items']


def make_app():
    app = Flask(__name__)
    app.config.from_object('mongorest.DefaultSettings')
    app.config.from_envvar('MONGOREST_SETTINGS')
    from .mongo import mongo, OidConverter
    app.url_map.converters['oid'] = OidConverter
    app.register_blueprint(mongo)
    return app


app = make_app()


def main():
    app.run(host='0.0.0.0', port=8080, debug=True)


if __name__ == '__main__':
    main()
