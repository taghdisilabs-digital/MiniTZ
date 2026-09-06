using UnrealBuildTool;

public class BiellaGames : ModuleRules
{
	public BiellaGames(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput", "NavigationSystem", "UMG", "Niagara" });
		
		PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore", "Json", "AudioMixer", "RenderCore", "RHI", "AnimGraphRuntime", "AnimationCore", "BiellaLoadingScreen" });
		
		// Uncomment if you are using online features
		// AddModuleNamesWithExcludedFromBuild("OnlineSubsystem");
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");
		
		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
