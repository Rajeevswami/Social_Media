from __future__ import annotations

from rest_framework import serializers

from ai_companion.models import MoodCheck, WellbeingNudge


class CaptionRequestSerializer(serializers.Serializer):
    idea = serializers.CharField(min_length=2, max_length=300, trim_whitespace=True)
    tone = serializers.ChoiceField(
        choices=("casual", "witty", "inspirational", "professional"), required=False
    )
    count = serializers.IntegerField(min_value=1, max_value=3, default=3)


class CaptionResponseSerializer(serializers.Serializer):
    suggestions = serializers.ListField(child=serializers.CharField())
    provider = serializers.CharField(allow_blank=True, required=False)


class ModeratePreviewSerializer(serializers.Serializer):
    text = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=True)


class MoodCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodCheck
        fields = ("id", "signal", "suggestion", "posts_analyzed", "negative_streak", "created_at")
        read_only_fields = fields


class NudgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WellbeingNudge
        fields = ("id", "message", "created_at", "dismissed_at", "is_active")
        read_only_fields = fields
