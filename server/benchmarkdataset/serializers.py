from rest_framework import serializers
from django.utils import timezone
from benchmark.models import Benchmark
from dataset.models import Dataset

from .models import BenchmarkDataset
from utils.associations import (
    validate_approval_status_on_creation,
    validate_approval_status_on_update,
    should_auto_approve_dataset,
)


class BenchmarkDatasetListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BenchmarkDataset
        read_only_fields = ["initiated_by", "approved_at"]
        fields = "__all__"

    def validate(self, data):
        bid = self.context["request"].data.get("benchmark")
        dataset = self.context["request"].data.get("dataset")
        approval_status = self.context["request"].data.get("approval_status", "PENDING")

        benchmark = Benchmark.objects.get(pk=bid)

        # benchmark approval status
        benchmark_approval_status = benchmark.approval_status
        if benchmark_approval_status != "APPROVED":
            raise serializers.ValidationError(
                "Association requests can be made only on an approved benchmark"
            )

        # dataset state
        dataset_obj = Dataset.objects.get(pk=dataset)
        dataset_state = dataset_obj.state
        if dataset_state != "OPERATION":
            raise serializers.ValidationError(
                "Association requests can be made only on an operational dataset"
            )

        # dataset prep mlcube
        if dataset_obj.data_preparation_mlcube != benchmark.data_preparation_mlcube:
            raise serializers.ValidationError(
                "Dataset association request can be made only if the dataset"
                " was prepared with benchmark's data preparation container"
            )

        # approval status
        last_benchmarkdataset = (
            BenchmarkDataset.objects.filter(benchmark__id=bid, dataset__id=dataset)
            .order_by("-created_at")
            .first()
        )
        validate_approval_status_on_creation(last_benchmarkdataset, approval_status)

        return data

    def create(self, validated_data):
        approval_status = validated_data.get("approval_status", "PENDING")
        if approval_status != "PENDING":
            validated_data["approved_at"] = timezone.now()
        else:
            if should_auto_approve_dataset(
                validated_data["benchmark"],
                validated_data["dataset"],
                self.context["request"].user,
            ):
                validated_data["approval_status"] = "APPROVED"
                validated_data["approved_at"] = timezone.now()
        return BenchmarkDataset.objects.create(**validated_data)


class DatasetApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = BenchmarkDataset
        read_only_fields = ["initiated_by", "approved_at"]
        fields = [
            "approval_status",
            "initiated_by",
            "approved_at",
            "created_at",
            "modified_at",
        ]

    def validate(self, data):
        if not self.instance:
            raise serializers.ValidationError("No dataset association found")
        return data

    def validate_approval_status(self, cur_approval_status):
        last_approval_status = self.instance.approval_status
        initiated_user = self.instance.initiated_by
        current_user = self.context["request"].user
        validate_approval_status_on_update(
            last_approval_status, cur_approval_status, initiated_user, current_user
        )
        return cur_approval_status

    def update(self, instance, validated_data):
        if "approval_status" in validated_data:
            if validated_data["approval_status"] != instance.approval_status:
                instance.approval_status = validated_data["approval_status"]
                if instance.approval_status != "PENDING":
                    instance.approved_at = timezone.now()
        instance.save()
        return instance


class BenchmarkListofDatasetsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BenchmarkDataset
        fields = ["dataset", "approval_status", "created_at"]
