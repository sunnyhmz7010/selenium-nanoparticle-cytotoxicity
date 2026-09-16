from pathlib import Path

from src.data import add_derived_features, build_analysis_subset, feature_groups, load_senp_dataset, make_group_ids


DATA_PATH = Path("data/senp/senp_validation_dataset_final.csv")


def test_load_senp_dataset_keeps_the_curated_selenium_rows():
    frame = load_senp_dataset(DATA_PATH)

    assert len(frame) == 383
    assert frame["Material"].notna().all()
    assert frame["Material"].astype(str).str.contains("Se").all()
    assert not frame["Material"].astype(str).str.contains("Na₂SeO₃|Na2SeO3").any()


def test_build_analysis_subset_applies_the_mtt_target_contract():
    frame = build_analysis_subset(load_senp_dataset(DATA_PATH))

    assert len(frame) == 205
    assert frame["Cell_Viability (%)"].notna().all()
    assert frame["Time (hr)"].notna().all()
    assert frame["Concentration (ug/ml)"].notna().all()
    assert frame["group_id"].notna().all()
    assert frame["log_concentration"].ge(0).all()


def test_feature_groups_keep_ic50_out_of_the_primary_sets():
    groups = feature_groups()

    assert "IC50_uM" not in groups["baseline"]
    assert "IC50_uM" not in groups["chemistry_no_ic50"]
    assert "IC50_uM" in groups["ic50_assisted"]
    assert set(groups["chemistry_no_ic50"]) > set(groups["baseline"])


def test_group_ids_fall_back_to_article_id_when_doi_is_missing():
    frame = {"DOI": [None, "10/example"], "Article_ID": [7, 8]}

    groups = make_group_ids(frame)

    assert groups.tolist() == ["article:7", "doi:10/example"]


def test_derived_features_can_be_built_before_endpoint_filtering():
    frame = add_derived_features(load_senp_dataset(DATA_PATH))

    assert "size_final" in frame.columns
    assert "log_concentration" in frame.columns
    assert len(frame) == 383
