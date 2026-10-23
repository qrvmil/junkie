# Hit Single ↔ Garn47 contract

## Launch and save boundary

The packaged Hit Single executable refers to:

- `assets/garn/garn47`
- the Windows `.exe` suffix
- the default window name `garn47`
- `AppData/ShadowMario/NightmareVision`
- the `.garnular` save suffix

Garn47 Python scripts append unlock tokens to:

```text
%APPDATA%\ShadowMario\NightmareVision\garn47.garnular
```

Setting `APPDATA` alone is insufficient on POSIX: all 16 save blocks run
`.replace('/', '\\')`, turning the entire absolute path into a filename
containing literal backslashes. The recovered Blender text blocks therefore
need a narrow source transformation to `os.path.join`, while retaining the
same `ShadowMario/NightmareVision/garn47.garnular` suffix. The rebuilt Haxe
connector must resolve the same Application Support location and use a
platform-specific native-app launch path and process check.

## Confirmed unlock tokens

| Event | Appended token |
| --- | --- |
| Spire | `theformspiretakesoffwithitschambers` |
| Broadcasted | `broadcastedtotheearsoftheworld` |
| Bus | `escapingallyourtroublestoanewlife` |
| Car Zero | `carnewlikethecarold` |
| Marblob | `ablobinaworldofcubes` |
| Giraffe | `giraffethatslipslikeice` |
| Silver Garn | `youarenowthecountdownmode49307153164329` |
| Golden Garn | `youarenowthecounterdowner02813927613928` |
| Quiz | `wowyouknowalotaboutgarn` |
| Car's Little Song | `carsingsalittlesongforyou` |
| The Power of Pig | `themightypigeatsthetruffle` |
| Tri-torial | `tritorialfortheagesandfingers` |
| So Retro | `retrographicsliketheolddays` |

## CodeGraph findings

The recovered scripts that write the save use the same Windows-specific
`APPDATA` expression. Representative blocks include the create scripts for
Broadcasted, Bus, Car Zero, and other unlockable entities. A second family of
15 scripts writes small secret text files to Windows Desktop/OneDrive paths;
those also require `pathlib`/`os.path` handling on macOS.

CodeGraph also found third-party `EO_network` and `EO_config` modules; they are
not yet proven to be part of the normal single-player execution path and should
not drive platform changes until runtime tracing says otherwise.
