using UnrealBuildTool;

public class BiellaLoadingScreen : ModuleRules
{
    public BiellaLoadingScreen(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "SlateCore" });
        PrivateDependencyModuleNames.AddRange(new[] {
            "CoreUObject", "Slate", "PreLoadScreen", "RHI"
        });
    }
}
