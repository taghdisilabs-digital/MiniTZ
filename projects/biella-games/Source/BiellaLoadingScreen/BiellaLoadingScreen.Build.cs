using UnrealBuildTool;

public class BiellaLoadingScreen : ModuleRules
{
    public BiellaLoadingScreen(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PrivateDependencyModuleNames.AddRange(new[] {
            "Core", "Slate", "SlateCore", "PreLoadScreen", "RHI"
        });
    }
}
