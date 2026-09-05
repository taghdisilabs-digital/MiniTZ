using UnrealBuildTool;

public class BiellaGames : ModuleRules
{
	public BiellaGames(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput", "NavigationSystem" });
		
		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.Add("Slate");
		// PrivateDependencyModuleNames.Add("SlateCore");
		
		// Uncomment if you are using online features
		// AddModuleNamesWithExcludedFromBuild("OnlineSubsystem");
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");
		
		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
