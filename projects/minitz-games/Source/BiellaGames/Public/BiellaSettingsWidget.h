// Copyright Biella Games. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "BiellaSettingsWidget.generated.h"

class UButton;
class UCanvasPanel;
class UCheckBox;
class USlider;
class UTextBlock;

/** Native pause/settings surface; every control is wired to a live subsystem. */
UCLASS()
class BIELLAGAMES_API UBiellaSettingsWidget : public UUserWidget
{
    GENERATED_BODY()

public:
    virtual void NativeConstruct() override;

    void OpenSettings();
    void CloseSettings();
    bool IsSettingsOpen() const;
    void RefreshFromSettings();
    void ApplyAndSave();

    UFUNCTION(BlueprintPure, Category="Biella|Settings")
    float GetSensitivityXControlValue() const;

    UFUNCTION(BlueprintPure, Category="Biella|Settings")
    float GetSensitivityYControlValue() const;

    UFUNCTION(BlueprintPure, Category="Biella|Settings")
    float GetHUDScaleControlValue() const;

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    void BuildLayout();

private:
    UFUNCTION()
    void OnSensitivityXChanged(float Value);

    UFUNCTION()
    void OnSensitivityYChanged(float Value);

    UFUNCTION()
    void OnInvertYChanged(bool bIsChecked);

    UFUNCTION()
    void OnMotionBlurChanged(bool bIsChecked);

    UFUNCTION()
    void OnHUDScaleChanged(float Value);

    UFUNCTION()
    void OnApplyResumeClicked();

    void ApplyLiveSettings();
    void UpdateValueLabels();
    static float FromNormalized(float Value, float Min, float Max);
    static float ToNormalized(float Value, float Min, float Max);

    UPROPERTY(Transient)
    TObjectPtr<UCanvasPanel> RootCanvas;

    UPROPERTY(Transient)
    TObjectPtr<USlider> SensitivityXSlider;

    UPROPERTY(Transient)
    TObjectPtr<USlider> SensitivityYSlider;

    UPROPERTY(Transient)
    TObjectPtr<UCheckBox> InvertYCheckBox;

    UPROPERTY(Transient)
    TObjectPtr<UCheckBox> MotionBlurCheckBox;

    UPROPERTY(Transient)
    TObjectPtr<USlider> HUDScaleSlider;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> SensitivityXValue;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> SensitivityYValue;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> HUDScaleValue;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> InvertYValue;

    UPROPERTY(Transient)
    TObjectPtr<UTextBlock> MotionBlurValue;

    bool bRefreshingControls = false;
};
