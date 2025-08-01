from rest_framework import serializers


def validate_approval_status_on_creation(last_association, approval_status):
    if not last_association:
        if approval_status != "PENDING":
            raise serializers.ValidationError(
                "User can approve or reject association request only if there are prior requests"
            )
    else:
        if approval_status == "PENDING":
            if last_association.approval_status != "REJECTED":
                raise serializers.ValidationError(
                    "User can create a new request only if prior request is rejected"
                )
        elif approval_status == "APPROVED":
            raise serializers.ValidationError(
                "User cannot create an approved association request"
            )
        # approval_status == "REJECTED":
        else:
            if last_association.approval_status != "APPROVED":
                raise serializers.ValidationError(
                    "User can reject request only if prior request is approved"
                )


def validate_approval_status_on_update(
    last_approval_status, cur_approval_status, initiated_user, current_user
):
    if last_approval_status != "PENDING":
        raise serializers.ValidationError(
            "User can approve or reject only a pending request"
        )
    if cur_approval_status == "APPROVED":
        if current_user.id == initiated_user.id:
            raise serializers.ValidationError(
                "Same user cannot approve the association request"
            )


def __should_auto_approve(
    benchmark, component, initiating_user, auto_approve_mode, auto_approve_allow_list
):
    same_owner = component.owner.id == benchmark.owner.id
    if same_owner:
        return True

    if initiating_user.id == benchmark.owner.id:
        return False

    always_auto_approve = auto_approve_mode == "ALWAYS"
    if always_auto_approve:
        return True

    auto_approve_from_allow_list = (
        auto_approve_mode == "ALLOWLIST"
        and component.owner.email in auto_approve_allow_list
    )
    return auto_approve_from_allow_list


def should_auto_approve_dataset(benchmark, dataset, initiating_user):
    return __should_auto_approve(
        benchmark,
        dataset,
        initiating_user,
        benchmark.dataset_auto_approval_mode,
        benchmark.dataset_auto_approval_allow_list,
    )


def should_auto_approve_model(benchmark, model, initiating_user):
    return __should_auto_approve(
        benchmark,
        model,
        initiating_user,
        benchmark.model_auto_approval_mode,
        benchmark.model_auto_approval_allow_list,
    )
