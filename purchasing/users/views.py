# -*- coding: utf-8 -*-

from flask import (
    render_template, request, flash,
    current_app, url_for, redirect
)

from flask_security import current_user, login_required

from purchasing.database import db
from purchasing.users.forms import DepartmentForm

from purchasing.users import blueprint

@blueprint.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    '''View to update user model with data passed through form after validation
    '''
    form = DepartmentForm(obj=current_user)
    if form.validate_on_submit():
        user = current_user

        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.department = form.department.data
        db.session.commit()

        flash('Updated your profile!', 'alert-success')
        current_app.logger.debug('PROFILE UPDATE: Updated profile for {email} with {data}'.format(
            email=user.email, data=form.data
        ))

        return redirect(url_for('users.profile'))

    return render_template('users/profile.html', form=form, user=current_user)
