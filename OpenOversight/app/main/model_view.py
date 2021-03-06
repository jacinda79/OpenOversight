from flask import render_template, redirect, request, url_for, flash, abort
from flask.views import MethodView
from flask_login import login_required, current_user
from ..auth.utils import ac_or_admin_required
from ..models import db
from ..utils import add_department_query, set_dynamic_default


class ModelView(MethodView):
    model = None
    model_name = ''
    per_page = 20
    order_by = ''  # this should be a field on the model
    descending = False  # used for order_by
    form = ''
    create_function = ''
    department_check = False

    def get(self, obj_id):
        if obj_id is None:
            if request.args.get('page'):
                page = int(request.args.get('page'))
            else:
                page = 1

            if self.order_by:
                if not self.descending:
                    objects = self.model.query.order_by(getattr(self.model, self.order_by)).paginate(page, self.per_page, False)
                objects = self.model.query.order_by(getattr(self.model, self.order_by).desc()).paginate(page, self.per_page, False)
            else:
                objects = self.model.query.paginate(page, self.per_page, False)

            return render_template('{}_list.html'.format(self.model_name), objects=objects, url='main.{}_api'.format(self.model_name))
        else:
            obj = self.model.query.get_or_404(obj_id)
            return render_template('{}_detail.html'.format(self.model_name), obj=obj, current_user=current_user)

    @login_required
    @ac_or_admin_required
    def new(self, form=None):
        if not form:
            form = self.get_new_form()
            if form.department:
                add_department_query(form, current_user)
                if getattr(current_user, 'dept_pref_rel', None):
                    set_dynamic_default(form.department, current_user.dept_pref_rel)
            if form.creator_id and not form.creator_id.data:
                form.creator_id.data = current_user.id
            if form.last_updated_id:
                form.last_updated_id.data = current_user.id

        if form.validate_on_submit():
            new_instance = self.create_function(form)
            db.session.add(new_instance)
            db.session.commit()
            flash('{} created!'.format(self.model_name))
            return redirect(url_for('main.{}_api'.format(self.model_name), obj_id=new_instance.id, _method='GET'))

        return render_template('{}_new.html'.format(self.model_name), form=form)

    @login_required
    @ac_or_admin_required
    def edit(self, obj_id, form=None):
        obj = self.model.query.get_or_404(obj_id)
        if self.department_check:
            if not current_user.is_administrator and current_user.ac_department_id != obj.department_id:
                abort(403)

        if not form:
            form = self.get_edit_form(obj)
            if obj.creator_id:
                form.creator_id.data = obj.creator_id
            else:
                form.creator_id.data = current_user.id
            form.last_updated_id.data = current_user.id

        if form.department:
            add_department_query(form, current_user)
        if form.validate_on_submit():
            self.populate_obj(form, obj)
            flash('{} successfully updated!'.format(self.model_name))
            return redirect(url_for('main.{}_api'.format(self.model_name), obj_id=obj_id, _method='GET'))

        return render_template('{}_edit.html'.format(self.model_name), obj=obj, form=form)

    @login_required
    @ac_or_admin_required
    def delete(self, obj_id):
        obj = self.model.query.get_or_404(obj_id)
        if self.department_check:
            if not current_user.is_administrator and current_user.ac_department_id != obj.department_id:
                abort(403)

        if request.method == 'POST':
            db.session.delete(obj)
            db.session.commit()

            return redirect(url_for('main.{}_api'.format(self.model_name)))

        return render_template('{}_delete.html'.format(self.model_name), obj=obj)

    def get_edit_form(self, obj):
        return self.form(request.form, obj=obj)

    def get_new_form(self):
        return self.form()

    def populate_obj(self, form, obj):
        form.populate_obj(obj)
        db.session.add(obj)

    def create_obj(self, form):
        self.model(**form.data)

    def dispatch_request(self, *args, **kwargs):
        end_of_url = request.url.split('/')[-1]
        endings = ['edit', 'new', 'delete']
        meth = None
        for ending in endings:
            if end_of_url == ending:
                meth = getattr(self, ending, None)
        if not meth:
            if request.method == 'GET':
                meth = getattr(self, 'get', None)
            else:
                assert meth is not None, 'Unimplemented method %r' % request.method
        return meth(*args, **kwargs)
