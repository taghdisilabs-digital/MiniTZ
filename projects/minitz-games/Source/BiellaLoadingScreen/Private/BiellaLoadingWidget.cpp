#include "BiellaLoadingWidget.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/SLeafWidget.h"
#include "Rendering/DrawElements.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Text/STextBlock.h"

// Geometry-only activity indication: no marquee texture, invented percentage,
// active timer, or game-thread update is needed by the loading Slate thread.
class SBiellaActivityIndicator final : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SBiellaActivityIndicator) {} SLATE_END_ARGS()
    void Construct(const FArguments&) { ForceVolatile(true); }
    virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(392, 4); }
    virtual int32 OnPaint(const FPaintArgs&, const FGeometry& Geometry, const FSlateRect&,
        FSlateWindowElementList& Elements, int32 Layer, const FWidgetStyle& Style, bool) const override
    {
        const FVector2f Size(Geometry.GetLocalSize());
        const FSlateBrush* Brush = FCoreStyle::Get().GetBrush("WhiteBrush");
        FSlateDrawElement::MakeBox(Elements, Layer, Geometry.ToPaintGeometry(), Brush,
            ESlateDrawEffect::None, FLinearColor(0.025f, 0.07f, 0.09f) * Style.GetColorAndOpacityTint());
        const float Width = Size.X * 0.24f;
        const float Phase = 0.5f + 0.5f * FMath::Sin(float(FMath::Fmod(FPlatformTime::Seconds(), 2.0)) * PI);
        FSlateDrawElement::MakeBox(Elements, Layer + 1,
            Geometry.ToPaintGeometry(FVector2f(Width, Size.Y), FSlateLayoutTransform(FVector2f((Size.X - Width) * Phase, 0))),
            Brush, ESlateDrawEffect::None, FLinearColor(0.16f, 0.68f, 0.78f) * Style.GetColorAndOpacityTint());
        return Layer + 1;
    }
};

TSharedRef<SWidget> CreateBiellaLoadingWidget()
{
    return SNew(SBorder)
            .BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FLinearColor(0.008f, 0.012f, 0.02f))
            .HAlign(HAlign_Center).VAlign(VAlign_Center)
            [
                SNew(SScaleBox).Stretch(EStretch::ScaleToFit)
                [
                    SNew(SBox).WidthOverride(440.f).Padding(24.f)
                    [
                        SNew(SVerticalBox)
                        + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center)
                        [
                            SNew(STextBlock).Text(NSLOCTEXT("BiellaLoading", "Title", "BIELLA"))
                            .Font(FCoreStyle::GetDefaultFontStyle("Bold", 42))
                            .ColorAndOpacity(FLinearColor(0.86f, 0.91f, 0.96f))
                        ]
                        + SVerticalBox::Slot().AutoHeight().Padding(0.f, 22.f, 0.f, 0.f)
                        [
                            SNew(SBox).HeightOverride(4.f)
                            [
                                SNew(SBiellaActivityIndicator)
                            ]
                        ]
                        + SVerticalBox::Slot().AutoHeight().HAlign(HAlign_Center).Padding(0.f, 18.f, 0.f, 0.f)
                        [
                            SNew(STextBlock).Text(NSLOCTEXT("BiellaLoading", "Preparing", "Preparing your world"))
                            .Font(FCoreStyle::GetDefaultFontStyle("Regular", 16))
                            .ColorAndOpacity(FLinearColor(0.56f, 0.65f, 0.73f))
                        ]
                    ]
                ]
            ];
}
