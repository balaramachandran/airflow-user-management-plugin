import airflow
from airflow.plugins_manager import AirflowPlugin
from airflow.contrib.auth.backends.password_auth import PasswordUser
from airflow.settings import Session
from airflow.models import User

from flask_login import current_user
from sqlalchemy import func

from flask_admin.babel import gettext
from flask_admin.contrib.sqla import ModelView

from flask import Markup
from flask import Blueprint, flash


from wtforms import PasswordField

import logging


"""
Notes: User object has a superuser variable, but its not an actual column in the DB
"""


def email_formatter(v, c, m, p):
    return Markup('<a href="mailto:{m.email}">{m.email}</a>'.format(**locals()))

class UserManagementModelView(ModelView):

    # http://flask-admin.readthedocs.io/en/latest/api/mod_model/

    verbose_name_plural = "Change Passwords"
    verbose_name = "Change Password"
    list_template = 'airflow/model_list.html'
    edit_template = 'airflow/model_edit.html'
    create_template = 'airflow/model_create.html'

    column_display_actions = True
    # page_size = 500
    can_set_page_size = True

    can_create = True
    can_edit = True
    can_delete = True

    column_list = ('id', 'username', 'email')
    column_formatters = dict(email=email_formatter)
    column_searchable_list = ('username', 'email')


    form_columns = ('username', 'email', 'password')
    form_widget_args = {
        'password': {
            'type': "password"
        }
    }

    # Added validation to make sure only the user itself or the Admin can change the details.
    def on_form_prefill(self, form, id):
        if (current_user.user.username != form.username.data and current_user.user.username != 'admin'):
           flash('Trying to edit wrong user {u} while logged in as {cu}'.format(u=form.username.data, cu=current_user.user.username), 'error')
           form.username.render_kw = {'readonly': True}
           form.password.render_kw = {'readonly': True}
           form.email.render_kw = {'readonly': True}

    # Added the override for get_query so that the admin can see all the users while other's can see only their record displayed.
    def get_query(self):
        if current_user.user.username == 'admin':
           return self.session.query(self.model)

        return  self.session.query(self.model).filter(self.model.username==username)

    # Added the override for get_count_query so that the admin can see the count of all users while other's can see only one row displayed.
    def get_count_query(self):
        if current_user.user.username == 'admin':
           return self.session.query(func.count('*')).filter(self.model.username!='')

        return  self.session.query(func.count('*')).filter(self.model.username==username)

    def on_model_change(self, form, model, is_created):

        return super().on_model_change(form, model, is_created)

    # Overrides the create_model function to create the User object required to create the PasswordUser object
    def create_model(self, form):
        logging.info("UserManagementModelView.create_model(form=" + str(form) + ")")
        # Only the Admin can create new user from this plugin.
        if current_user.user.username != 'admin':
           flash('Failed to create user. Only admin user can create new user', 'error')
           logging.exception('Failed to create new user.')
           return False
           
        try:
            user = User() # Added this line to create the user object since its required to create the passworduser object
            model = self.model(user)
            form.populate_obj(model)
            self.session.add(model)
            self.on_model_change(form, model, True)
            self.session.commit()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(gettext('Failed to create record. %(error)s', error=str(ex)), 'error')
                logging.exception('Failed to create record.')

            self.session.rollback()

            return False
        else:
            self.after_model_change(form, model, True)

        return model

    def update_model(self, form, model):
        # if model.username == self.cur_user :
        logging.info("UserManagementModelView.update_model(form=" + str(form) + ", model=" + str(model) + ")")
        return super(UserManagementModelView, self).update_model(form, model)

    def delete_model(self, model):
        logging.info("UserManagementModelView.delete_model(model=" + str(model) + ")")
        return super(UserManagementModelView, self).delete_model(model)


# Creating View to be used by Plugin
user_management = UserManagementModelView(PasswordUser, Session, name="Change Password", category="Admin", url="change_password")

# Creating Blueprint
user_management_bp = Blueprint(
    "user_management_bp",
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/static/'
)


# Creating the UserManagementPlugin which extends the AirflowPlugin so its imported into Airflow
class UserManagementPlugin(AirflowPlugin):
    name = "user_management"
    operators = []
    flask_blueprints = [user_management_bp]
    hooks = []
    executors = []
    admin_views = [user_management]
    menu_links = []
    
