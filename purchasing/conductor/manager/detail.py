# -*- coding: utf-8 -*-

import datetime
import pytz

from sqlalchemy.exc import IntegrityError

from flask import (
    abort, redirect, url_for, current_app, request,
    session, render_template, flash
)

from flask_login import current_user

from purchasing.database import db, get_or_create
from purchasing.decorators import requires_roles
from purchasing.utils import localize_datetime

from purchasing.data.contracts import ContractBase
from purchasing.data.flows import Flow
from purchasing.data.contract_stages import ContractStage, ContractStageActionItem

from purchasing.users.models import User

from purchasing.conductor.forms import (
    NoteForm, SendUpdateForm, PostOpportunityForm,
    ContractMetadataForm, CompleteForm, NewContractForm
)

from purchasing.conductor.util import (
    UpdateFormObj, ConductorToBeaconObj, ContractMetadataObj,
    assign_a_contract
)

from purchasing.conductor.manager import blueprint

@blueprint.route('/contract/<int:contract_id>', methods=['GET', 'POST'])
@blueprint.route('/contract/<int:contract_id>/stage/<int:stage_id>', methods=['GET', 'POST'])
@requires_roles('conductor', 'admin', 'superadmin')
def detail(contract_id, stage_id=-1):
    '''View to control an individual stage update process

    This is the primary view for conductor. All actions that users can
    take with a :py:class:`~purchasing.data.contracts.ContractBase` flow
    through here.

    .. seealso::
        There are a number of forms that are used on this page to allow
        the users to do actions directly from the management step:

        * :py:class:`~purchasing.conductor.forms.NoteForm` to allow
          users to take notes
        * :py:class:`~purchasing.conductor.forms.SendUpdateForm` to allow
          users to send email updates
        * :py:class:`~purchasing.conductor.forms.PostOpportunityForm` to allow
          users to post opportunities directly to :doc:`/beacon`
        * :py:class:`~purchasing.conductor.forms.ContractMetadataForm` to allow
          users to update a contract's metadata
        * :py:class:`~purchasing.conductor.forms.CompleteForm` to allow
          users to transition to the next :py:class:`~purchasing.data.stages.Stage`
          in the contract's :py:class:`~purchasing.data.flows.Flow`

    :param contract_id: Primary key ID for a
        :py:class:`~purchasing.data.contracts.ContractBase`
    :param stage_id: Primary key ID for a
        :py:class:`~purchasing.data.contract_stages.ContractStage`

    :status 200: Render the detail
    :status 302: Post a specific form. This form will either transition
        to the next contract stage if it is a
        :py:class:`~purchasing.conductor.forms.CompleteForm`, or perform
        whatever action is in that form's ``post_validate_action`` method
    :status 404: Contract not found
    '''
    contract = ContractBase.query.get(contract_id)
    if not contract:
        abort(404)

    if contract.completed_last_stage():
        return redirect(url_for('conductor.edit', contract_id=contract.id))

    if stage_id == -1:
        # redirect to the current stage page
        contract_stage = contract.get_current_stage()

        if contract_stage:
            return redirect(url_for(
                'conductor.detail', contract_id=contract_id, stage_id=contract_stage.id
            ))
        current_app.logger.warning('Could not find stages for this contract, aborting!')
        abort(500)

    stages = contract.get_contract_stages()

    try:
        active_stage = [i for i in stages if i.id == stage_id][0]
        current_stage = [i for i in stages if i.entered and not i.exited][0]
        if active_stage.entered is None:
            abort(404)
    except IndexError:
        abort(404)

    note_form = NoteForm()
    update_form = SendUpdateForm(obj=UpdateFormObj(current_stage))
    opportunity_form = PostOpportunityForm(
        obj=contract.opportunity if contract.opportunity else ConductorToBeaconObj(contract)
    )
    metadata_form = ContractMetadataForm(obj=ContractMetadataObj(contract))
    complete_form = CompleteForm()

    if session.get('invalid_date-{}'.format(contract_id), False):
        complete_form.errors['complete'] = session.pop('invalid_date-{}'.format(contract_id))

    forms = {
        'activity': note_form, 'update': update_form,
        'post': opportunity_form, 'update-metadata': metadata_form
    }

    active_tab = '#activity'

    submitted_form_name = request.args.get('form', None)

    if submitted_form_name:
        submitted_form = forms[submitted_form_name]

        if submitted_form.validate_on_submit():
            action = ContractStageActionItem(
                contract_stage_id=stage_id, action_type=submitted_form_name,
                taken_by=current_user.id, taken_at=datetime.datetime.utcnow()
            )
            action = submitted_form.post_validate_action(action, contract, current_stage)

            db.session.add(action)
            db.session.commit()

            return redirect(url_for(
                'conductor.detail', contract_id=contract_id, stage_id=stage_id
            ))
        else:
            active_tab = '#' + submitted_form_name

    actions = contract.filter_action_log()
    # actions = contract.build_complete_action_log()
    subscribers, total_subscribers = contract.build_subscribers()
    flows = Flow.query.filter(Flow.id != contract.flow_id).all()

    current_app.logger.info(
        'CONDUCTOR DETAIL VIEW - Detail view for contract {} (ID: {}), stage {}'.format(
            contract.description, contract.id, current_stage.name
        )
    )

    opportunity_form.display_cleanup()
    if len(stages) > 0:
        return render_template(
            'conductor/detail.html',
            stages=stages, actions=actions, active_tab=active_tab,
            note_form=note_form, update_form=update_form,
            opportunity_form=opportunity_form, metadata_form=metadata_form,
            complete_form=complete_form, contract=contract,
            current_user=current_user, active_stage=active_stage,
            current_stage=current_stage, flows=flows, subscribers=subscribers,
            total_subscribers=total_subscribers,
            current_stage_enter=localize_datetime(current_stage.entered),
            categories=opportunity_form.get_categories(),
            subcategories=opportunity_form.get_subcategories()
        )
    abort(404)

@blueprint.route('/contract/<int:contract_id>/stage/<int:stage_id>/transition', methods=['GET', 'POST'])
@requires_roles('conductor', 'admin', 'superadmin')
def transition(contract_id, stage_id):
    '''Transition a contract from one date to the next date

    :param contract_id: Primary key ID for a
        :py:class:`~purchasing.data.contracts.ContractBase`
    :param stage_id: Primary key ID for a
        :py:class:`~purchasing.data.contract_stages.ContractStage`

    .. seealso::
        For the transition, see the
        :py:meth:`~purchasing.data.contracts.ContractBase.transition`
        method directly

    :status 302: Perform the transition, and redirect back to the detail view
        with either the new stage or the appropriate error message
    :status 404: Contract not found
    '''
    contract = ContractBase.query.get(contract_id)
    stage = ContractStage.query.filter(ContractStage.id == stage_id).first()
    complete_form = CompleteForm(started=stage.entered)

    if (request.method == 'POST' and complete_form.validate_on_submit()) or (request.method == 'GET'):
        if request.method == 'POST':
            completed_time = current_app.config['DISPLAY_TIMEZONE'].localize(
                complete_form.complete.data
            ).astimezone(pytz.UTC).replace(tzinfo=None)
        else:
            completed_time = datetime.datetime.utcnow()

        if not contract:
            abort(404)

        clicked = int(request.args.get('destination')) if \
            request.args.get('destination') else None

        try:
            actions = contract.transition(
                current_user, destination=clicked,
                complete_time=completed_time
            )

            for action in actions:
                db.session.add(action)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            pass
        except Exception:
            db.session.rollback()
            raise

        current_app.logger.info(
            'CONDUCTOR TRANSITION - Contract for {} (ID: {}) transition to {}'.format(
                contract.description, contract.id, contract.current_stage.name
            )
        )

        if contract.completed_last_stage():
            url = url_for('conductor.edit', contract_id=contract.id)
        else:
            url = url_for('conductor.detail', contract_id=contract.id)

        return redirect(url)

    session['invalid_date-{}'.format(contract_id)] = complete_form.errors['complete'][0]
    return redirect(url_for('conductor.detail', contract_id=contract.id))

@blueprint.route('/contract/<int:contract_id>/stage/<int:stage_id>/extend')
@requires_roles('conductor', 'admin', 'superadmin')
def extend(contract_id, stage_id):
    '''Extend a contract

    :param contract_id: Primary key ID for a
        :py:class:`~purchasing.data.contracts.ContractBase`
    :param stage_id: Primary key ID for a
        :py:class:`~purchasing.data.contract_stages.ContractStage`

    .. seealso::
        See :py:meth:`~purchasing.data.contract_stages.ContractStage.log_extension`
        for information about thea actual extend logging, and
        :py:meth:`~purchasing.data.contract_stages.ContractStage.extend`
        for more on the extend event itself

    :status 302: Redirect to the the contract edit view
    :status 404: Contract not found
    '''
    contract = ContractBase.query.get(contract_id)
    if not contract:
        abort(404)

    extend_action = contract.parent.extend(delete_children=False)
    current_app.logger.info(
        'CONDUCTOR EXTEND - Contract for {} (ID: {}) extended'.format(
            contract.parent.description, contract.parent.id
        )
    )
    extend_action = contract.current_contract_stage.log_extension(current_user)
    db.session.add(extend_action)
    db.session.commit()

    flash(
        'This contract has been extended. Please add the new expiration date below.',
        'alert-warning'
    )

    session['extend-{}'.format(contract.parent.id)] = True
    return redirect(url_for(
        'conductor.edit', contract_id=contract.parent.id
    ))


@blueprint.route('/contract/<int:contract_id>/stage/<int:stage_id>/flow-switch/<int:flow_id>')
@requires_roles('conductor', 'admin', 'superadmin')
def flow_switch(contract_id, stage_id, flow_id):
    '''Switch a contract's flow

    :param contract_id: Primary key ID for a
        :py:class:`~purchasing.data.contracts.ContractBase`
    :param stage_id: Primary key ID for a
        :py:class:`~purchasing.data.contract_stages.ContractStage`
    :param flow_id: Primary key ID for a
        :py:class:`~purchasing.data.flows.Flow`

    .. seealso::
        See :py:meth:`~purchasing.data.contracts.ContractBase.switch_flow`
        for more on the flow-switch logic

    :status 302: Redirect to the detail view for the first stage of the
        new flow
    :status 404: Contract not found
    '''
    contract = ContractBase.query.get(contract_id)
    if not contract:
        abort(404)

    new_contract_stage, contract = contract.switch_flow(
        flow_id, current_user
    )

    current_app.logger.info(
        'CONDUCTOR FLOW SWITCH - Contract for {} (ID: {}) switched to new flow {}'.format(
            contract.description, contract.id, contract.flow.flow_name
        )
    )
    return redirect(url_for(
        'conductor.detail', contract_id=contract_id, stage_id=new_contract_stage.id
    ))

@blueprint.route('/contract/<int:contract_id>/remove')
@requires_roles('conductor', 'admin', 'superadmin')
def remove(contract_id):
    '''Remove a contract from conductor

    We do this by setting the `is_visible` flag to False,
    which won't affect the contract's visibility on :doc:`/scout`
    but will remove it from the conductor "all contracts" list.

    :param contract_id: Primary key ID for a
        :py:class:`~purchasing.data.contracts.ContractBase`

    :status 302: Set contract visibility to false and redirect to
        the conductor index view
    :status 404: Contract not found
    '''
    contract = ContractBase.query.get(contract_id)
    if contract:
        contract.is_visible = False
        db.session.commit()
        current_app.logger.info(
            'CONDUCTOR REMOVE - Contract for {} (ID: {}) killed'.format(
                contract.description, contract.id
            )
        )
        flash('Successfully removed {} from conductor!'.format(contract.description), 'alert-success')
        return redirect(url_for('conductor.index'))
    abort(404)

@blueprint.route('/contract/<int:contract_id>/kill')
@requires_roles('conductor', 'admin', 'superadmin')
def kill_contract(contract_id):
    '''Remove a contract from conductor and scout

    :param contract_id: Primary key ID for a
        :py:class:`~purchasing.data.contracts.ContractBase`

    .. seealso::
        See :py:meth:`~purchasing.data.contracts.ContractBase.kill`
        for more on the kill logic

    :status 302: Remove the contract entirely and redirect to the index page
    :status 404: Contract not found
    '''
    contract = ContractBase.query.get(contract_id)
    if contract:
        flash_description = contract.description
        contract.kill()
        db.session.commit()
        current_app.logger.info(
            'CONDUCTOR KILL - Contract for {} (ID: {}) killed'.format(
                flash_description, contract.id
            )
        )
        flash('Successfully removed {} from use!'.format(flash_description), 'alert-success')
        return redirect(url_for('conductor.index'))
    abort(404)

@blueprint.route('/contract/<int:contract_id>/stage/<int:stage_id>/note/<int:note_id>/delete')
@requires_roles('conductor', 'admin', 'superadmin')
def delete_note(contract_id, stage_id, note_id):
    '''Delete a note from a conductor step

    :param contract_id: Primary key ID for a
        :py:class:`~purchasing.data.contracts.ContractBase`
    :param stage_id: Primary key ID for a
        :py:class:`~purchasing.data.contract_stages.ContractStage`
    :param note_id: Primary key ID for a
        :py:class:`~purchasing.data.contract_stages.ContractStageActionItem`

    :status 302: Deletes the note and redirects to the conductor
        detail view
    '''
    try:
        note = ContractStageActionItem.query.get(note_id)
        if note:
            current_app.logger.info('Conductor note delete')
            note.delete()
            flash('Note deleted successfully!', 'alert-success')
        else:
            flash("That note doesn't exist!", 'alert-warning')
    except Exception, e:
        current_app.logger.error('Conductor note delete error: {}'.format(str(e)))
        flash('Something went wrong: {}'.format(e.message), 'alert-danger')
    return redirect(url_for('conductor.detail', contract_id=contract_id))

@blueprint.route('/contract/<int:contract_id>/assign/<int:user_id>')
@requires_roles('conductor', 'admin', 'superadmin')
def reassign(contract_id, user_id):
    '''Reassign a contract to a new user

    :param contract_id: Primary key ID for a
        :py:class:`~purchasing.data.contracts.ContractBase`
    :param user_id: Primary key ID for a
        :py:class:`~purchasing.users.models.User`

    :status 302: Reassign a contract redirect to the conductor
        index view
    :status 404: Contract or user not found
    '''
    contract = ContractBase.query.get(contract_id)
    assignee = User.query.get(user_id)

    if not all([contract, assignee]):
        abort(404)

    if assignee.is_conductor():
        contract.assigned = assignee
        db.session.commit()
        flash('Successfully assigned {} to {}!'.format(contract.description, assignee.email), 'alert-success')
    else:
        flash('That user does not have the right permissions to be assigned a contract', 'alert-danger')

    return redirect(url_for('conductor.index'))

@blueprint.route('/contract/new', methods=['GET', 'POST'])
@blueprint.route('/contract/<int:contract_id>/start', methods=['GET', 'POST'])
@requires_roles('conductor', 'admin', 'superadmin')
def start_work(contract_id=-1):
    '''Start work on a contract

    When new work is started on a contract, a new contract is created
    (either as a clone of an existing contract, or as brand new work),
    assigned to the :py:class:`~purchasing.data.flows.Flow` and
    :py:class:`~purchasing.users.models.User` indicated in the
    :py:class:`~purchasing.conductor.forms.NewContractForm`

    :param contract_id: Primary key ID for a
        :py:class:`~purchasing.data.contracts.ContractBase`

    .. seealso::
        :py:meth:`~purchasing.data.contracts.ContractBase.clone` for
        more information on how new contracts get started, and
        :py:class:`~purchasing.conductor.forms.NewContractForm` for more
        on the form to start new work.

    :status 200: Render the new contract view
    :status 302: Create or start new work on a cloned contract
    '''
    contract = ContractBase.query.get(contract_id)

    if contract:
        first_stage = contract.get_first_stage()

        if first_stage and contract.completed_last_stage():
            pass
        elif first_stage and first_stage.stage_id != contract.current_stage_id:
            return redirect(url_for('conductor.detail', contract_id=contract.id))
        elif first_stage:
            contract.start = localize_datetime(contract.get_first_stage().entered)
    else:
        contract = ContractBase()
    form = NewContractForm(obj=contract)

    if form.validate_on_submit():
        if contract_id == -1:
            contract, _ = get_or_create(
                db.session, ContractBase, description=form.data.get('description'),
                department=form.data.get('department'), is_visible=False
            )
        elif not first_stage or contract.completed_last_stage():
            contract = ContractBase.clone(contract)
            contract.description = form.data.get('description')
            contract.department = form.data.get('department')
            db.session.add(contract)
            db.session.commit()

        assigned = assign_a_contract(
            contract, form.data.get('flow'), form.data.get('assigned'),
            start_time=form.data.get('start').astimezone(pytz.UTC).replace(tzinfo=None),
            clone=False
        )
        db.session.commit()

        if assigned:
            flash('Successfully assigned {} to {}!'.format(assigned.description, assigned.assigned.email), 'alert-success')
            return redirect(url_for('conductor.detail', contract_id=assigned.id))
        else:
            flash("That flow doesn't exist!", 'alert-danger')
    return render_template('conductor/new.html', form=form, contract_id=contract_id, contract=contract)
