 #encoding=utf-8

from flask import render_template, flash, redirect, session, url_for, request, make_response, g
from StringIO import StringIO
from html_convert import html2text
from config import POST_PRE_PAGE
from uploader import Uploader
from data_wrappers import DataWrappers
from blogapp import app
# from admin import admin
import os
import json
import re



date = DataWrappers()

def _html2text(html):
    sio = StringIO()
    html2text.html2text_file(html, sio.write)
    text = sio.getvalue()
    sio.close()
    return text
app.jinja_env.filters['html2text'] = _html2text


def global_map():
    tags = date.get_all_tags()
    links = date.get_all_links()
    map = {
         'tags': tags,
         'links': links,
    }
    return map


@app.before_request
def befor_request():
    g.user = date.get_first_user()


# @app.teardown_request
# def teardown_request():
# #   将mysql链接还给连接池，避免SAE的mysql gone away问题
#     db.session.remove()


@app.route('/')
@app.route('/blog')
@app.route('/blog/<int:page>')
def show_blog(page=1):
    if page < 1:
        page = 1
    p = date.get_entries_by_page(page=page, par_page=POST_PRE_PAGE)
    entries = p.items
    #页数标签
    if not p.total:
        pagination = [0]
    elif p.total % POST_PRE_PAGE != 0:
        pagination = range(1, p.total/POST_PRE_PAGE + 2)
    else:
        pagination = range(1, p.total/POST_PRE_PAGE + 1)

    return render_template('/blog/show_blog.html', entries=entries,
                           p=p, page=page, pagination=pagination,
                            **global_map())


@app.route('/category')
def show_categories():
    categories = date.get_all_categories()
    counts = date.get_entry_by_category(categories=categories)
    return render_template('blog/show_categories.html', categories=categories,
                           counts=counts, **global_map())


@app.route('/category/<int:category_id>')
def show_category(category_id):
    category = date.get_category_by_id(category_id)
    return render_template('/blog/show_category.html', category=category,
                           **global_map())

@app.route('/tag/<int:tag_id>')
def show_tag(tag_id):
    tag = date.get_tag_by_id(tag_id)

    return render_template('/blog/show_tag.html', tag=tag,
                           **global_map())


@app.route('/entry/<int:entry_id>')
def show_entry(entry_id):
    entry = date.get_entry_by_id(entry_id)
    date.increase_view_count(entry, 1)
    return render_template('/blog/show_entry.html', entry=entry,
                            **global_map())

@app.route('/entry/<int:entry_id>/prev')
def prev_entry(entry_id):
    entry = date.get_prev_entry(entry_id)
    if entry is None:
        return redirect(url_for('show_entry', entry_id=entry_id))
    return redirect(url_for('show_entry', entry_id=entry.id))


@app.route('/entry/<int:entry_id>/next')
def next_entry(entry_id):
    entry = date.get_next_entry(entry_id)
    if entry is None:
        return redirect(url_for('show_entry', entry_id=entry_id))
    return redirect(url_for('show_entry', entry_id=entry.id))

@app.route('/comment')
def show_comment():

    return render_template('blog/show_comment.html',
                           **global_map())

@app.route('/about')
def show_about():

    return render_template('blog/show_about.html',
                           **global_map())



# error dispose
@app.errorhandler(404)
def internal_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


@app.route('/login')
def admin_index():
    return render_template('index.html')


@app.route('/admin/create_entry', methods=['GET', 'POST'])
def admin_create_entry():

    return render_template('admin/create_entry.html')

@app.route('/upload/', methods=['GET', 'POST', 'OPTIONS'])
def upload():
    """UEditor文件上传接口

    config 配置文件
    result 返回结果
    """
    mimetype = 'application/json'
    result = {}
    action = request.args.get('action')

    # 解析JSON格式的配置文件
    with open(os.path.join(app.static_folder, 'ueditor', 'php',
                           'config.json')) as fp:
        try:
            # 删除 `/**/` 之间的注释
            CONFIG = json.loads(re.sub(r'\/\*.*\*\/', '', fp.read()))
        except:
            CONFIG = {}

    if action == 'config':
        # 初始化时，返回配置文件给客户端
        result = CONFIG

    elif action in ('uploadimage', 'uploadfile', 'uploadvideo'):
        # 图片、文件、视频上传
        if action == 'uploadimage':
            fieldName = CONFIG.get('imageFieldName')
            config = {
                "pathFormat": CONFIG['imagePathFormat'],
                "maxSize": CONFIG['imageMaxSize'],
                "allowFiles": CONFIG['imageAllowFiles']
            }
        elif action == 'uploadvideo':
            fieldName = CONFIG.get('videoFieldName')
            config = {
                "pathFormat": CONFIG['videoPathFormat'],
                "maxSize": CONFIG['videoMaxSize'],
                "allowFiles": CONFIG['videoAllowFiles']
            }
        else:
            fieldName = CONFIG.get('fileFieldName')
            config = {
                "pathFormat": CONFIG['filePathFormat'],
                "maxSize": CONFIG['fileMaxSize'],
                "allowFiles": CONFIG['fileAllowFiles']
            }

        if fieldName in request.files:
            field = request.files[fieldName]
            uploader = Uploader(field, config, app.static_folder)
            result = uploader.getFileInfo()
        else:
            result['state'] = '上传接口出错'

    elif action in ('uploadscrawl'):
        # 涂鸦上传
        fieldName = CONFIG.get('scrawlFieldName')
        config = {
            "pathFormat": CONFIG.get('scrawlPathFormat'),
            "maxSize": CONFIG.get('scrawlMaxSize'),
            "allowFiles": CONFIG.get('scrawlAllowFiles'),
            "oriName": "scrawl.png"
        }
        if fieldName in request.form:
            field = request.form[fieldName]
            uploader = Uploader(field, config, app.static_folder, 'base64')
            result = uploader.getFileInfo()
        else:
            result['state'] = '上传接口出错'

    elif action in ('catchimage'):
        config = {
            "pathFormat": CONFIG['catcherPathFormat'],
            "maxSize": CONFIG['catcherMaxSize'],
            "allowFiles": CONFIG['catcherAllowFiles'],
            "oriName": "remote.png"
        }
        fieldName = CONFIG['catcherFieldName']

        if fieldName in request.form:
            # 这里比较奇怪，远程抓图提交的表单名称不是这个
            source = []
        elif '%s[]' % fieldName in request.form:
            # 而是这个
            source = request.form.getlist('%s[]' % fieldName)

        _list = []
        for imgurl in source:
            uploader = Uploader(imgurl, config, app.static_folder, 'remote')
            info = uploader.getFileInfo()
            _list.append({
                'state': info['state'],
                'url': info['url'],
                'original': info['original'],
                'source': imgurl,
            })

        result['state'] = 'SUCCESS' if len(_list) > 0 else 'ERROR'
        result['list'] = _list

    else:
        result['state'] = '请求地址出错'

    result = json.dumps(result)

    if 'callback' in request.args:
        callback = request.args.get('callback')
        if re.match(r'^[\w_]+$', callback):
            result = '%s(%s)' % (callback, result)
            mimetype = 'application/javascript'
        else:
            result = json.dumps({'state': 'callback参数不合法'})

    res = make_response(result)
    res.mimetype = mimetype
    res.headers['Access-Control-Allow-Origin'] = '*'
    res.headers['Access-Control-Allow-Headers'] = 'X-Requested-With,X_Requested_With'
    return res