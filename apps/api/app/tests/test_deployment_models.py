from app.models.deployment import DeploymentStepKind, DeploymentStrategy, SecretReferenceProvider


def test_deployment_enums_are_stable():
    assert DeploymentStrategy.ROLLING.value == "rolling"
    assert DeploymentStepKind.MIGRATION.value == "migration"
    assert SecretReferenceProvider.DOCKER_SECRET.value == "docker_secret"


def test_batch24_deployment_tables_registered():
    from app.db.base import Base
    names = set(Base.metadata.tables)
    expected = {
        "deployment_environments", "deployment_service_profiles", "deployment_change_windows",
        "deployment_rollouts", "deployment_rollout_steps", "deployment_secret_references",
    }
    assert expected <= names
    assert len(names) == 252
