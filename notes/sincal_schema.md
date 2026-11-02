# PSS(R)SINCAL SQLite schema

Read from `database.db` (Lab 1, built and solved by SINCAL itself).

275 tables in the file, 33 of them populated.

## Populated tables

| Table | Rows |
| --- | ---: |
| CalcParameter | 1 |
| EcoCurrency | 1 |
| Element | 14 |
| FeederParameter | 1 |
| GlobalSetting | 1 |
| GraphicAreaTile | 1 |
| GraphicElement | 14 |
| GraphicLayer | 1 |
| GraphicNode | 10 |
| GraphicObjectType | 1 |
| GraphicTerminal | 22 |
| GraphicText | 46 |
| Infeeder | 1 |
| LFAccurResult | 1 |
| LFBranchResult | 12 |
| LFGroupResult | 1 |
| LFNodeResult | 5 |
| LFParNetLossesResult | 2 |
| LFPowBalanceResult | 1 |
| LFPowDataResult | 1 |
| Line | 6 |
| Load | 4 |
| NetworkGroup | 1 |
| Node | 10 |
| RelParameter | 1 |
| SC3BranchResult | 12 |
| SC3NodeResult | 5 |
| SynchronousMachine | 1 |
| Terminal | 22 |
| TwoWindingTransformer | 2 |
| Variant | 1 |
| Version | 1 |
| VoltageLevel | 2 |

## Columns of the tables the importer writes

### Node  (63 columns, 10 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `Node_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `Flag_Private` | INTEGER |  |  |  |
| 4 | `Name` | CHAR(50) |  |  |  |
| 5 | `ShortName` | CHAR(8) |  |  |  |
| 6 | `VoltLevel_ID` | INTEGER |  |  |  |
| 7 | `Group_ID` | INTEGER |  |  |  |
| 8 | `Zone_ID` | INTEGER |  |  |  |
| 9 | `EcoStation_ID` | INTEGER |  |  |  |
| 10 | `EcoField_ID` | INTEGER |  |  |  |
| 11 | `Flag_Type` | SMALLINT |  |  |  |
| 12 | `Busbar_ID` | INTEGER |  |  |  |
| 13 | `Equipment_ID` | INTEGER |  |  |  |
| 14 | `HarPCCdata_ID` | INTEGER |  |  |  |
| 15 | `Stp_ID` | INTEGER |  |  |  |
| 16 | `Ti` | DATE |  |  |  |
| 17 | `Ts` | DATE |  |  |  |
| 18 | `Flag_Diagram` | SMALLINT |  |  |  |
| 19 | `InclName` | CHAR(60) |  |  |  |
| 20 | `sh` | FLOAT |  |  |  |
| 21 | `Flag_Pos` | SMALLINT |  |  |  |
| 22 | `hr` | FLOAT |  |  |  |
| 23 | `hh` | FLOAT |  |  |  |
| 24 | `lat` | FLOAT |  |  |  |
| 25 | `lon` | FLOAT |  |  |  |
| 26 | `TextVal` | TEXT |  |  |  |
| 27 | `Uref` | FLOAT |  |  |  |
| 28 | `Un` | FLOAT |  |  |  |
| 29 | `Phi` | FLOAT |  |  |  |
| 30 | `Flag_Phase` | SMALLINT |  |  |  |
| 31 | `AddFaultData_ID` | INTEGER |  |  |  |
| 32 | `Ik2` | FLOAT |  |  |  |
| 33 | `tkr` | FLOAT |  |  |  |
| 34 | `Ip` | FLOAT |  |  |  |
| 35 | `Iamax` | FLOAT |  |  |  |
| 36 | `Uul` | FLOAT |  |  |  |
| 37 | `Ull` | FLOAT |  |  |  |
| 38 | `Flag_Reliability` | SMALLINT |  |  |  |
| 39 | `BusbarType_ID` | INTEGER |  |  |  |
| 40 | `SwitchBay1_ID` | INTEGER |  |  |  |
| 41 | `SwitchBay2_ID` | INTEGER |  |  |  |
| 42 | `Flag_HK` | SMALLINT |  |  |  |
| 43 | `Flag_ABW` | SMALLINT |  |  |  |
| 44 | `Flag_UM` | SMALLINT |  |  |  |
| 45 | `UM_Node_ID` | INTEGER |  |  |  |
| 46 | `T_UM` | FLOAT |  |  |  |
| 47 | `Flag_VER` | SMALLINT |  |  |  |
| 48 | `VER_Node_ID` | INTEGER |  |  |  |
| 49 | `Flag_VERP` | SMALLINT |  |  |  |
| 50 | `T_VER` | FLOAT |  |  |  |
| 51 | `p_VER` | FLOAT |  |  |  |
| 52 | `ci` | FLOAT |  |  |  |
| 53 | `Cs` | FLOAT |  |  |  |
| 54 | `cm` | FLOAT |  |  |  |
| 55 | `coo` | FLOAT |  |  |  |
| 56 | `Tl` | FLOAT |  |  |  |
| 57 | `m` | FLOAT |  |  |  |
| 58 | `Report_No` | INTEGER |  |  |  |
| 59 | `Flag_Volt` | SMALLINT |  |  |  |
| 60 | `RefNode_ID` | INTEGER |  |  |  |
| 61 | `Uul1` | FLOAT |  |  |  |
| 62 | `Ull1` | FLOAT |  |  |  |

Example row (non-empty fields only):

```
Node_ID=1, Variant_ID=1, Flag_Variant=1, Name='B01 Grid', ShortName='B01', VoltLevel_ID=1, Group_ID=1, Flag_Type=2, Flag_Pos=2, Un=33.0, Flag_Phase=7, tkr=1.0, Flag_VERP=1, Report_No=1
```

### Line  (66 columns, 6 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `Element_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `Typ_ID` | INTEGER |  |  |  |
| 4 | `Flag_Typ_ID` | SMALLINT |  |  |  |
| 5 | `LineTyp` | CHAR(40) |  |  |  |
| 6 | `Flag_LineTyp` | SMALLINT |  |  |  |
| 7 | `Flag_Ll` | SMALLINT |  |  |  |
| 8 | `Un` | FLOAT |  |  |  |
| 9 | `l` | FLOAT |  |  |  |
| 10 | `ParSys` | FLOAT |  |  |  |
| 11 | `Flag_Mat` | SMALLINT |  |  |  |
| 12 | `r` | FLOAT |  |  |  |
| 13 | `alpha` | FLOAT |  |  |  |
| 14 | `x` | FLOAT |  |  |  |
| 15 | `fn` | FLOAT |  |  |  |
| 16 | `c` | FLOAT |  |  |  |
| 17 | `va` | FLOAT |  |  |  |
| 18 | `CoupData_ID` | INTEGER |  |  |  |
| 19 | `Flag_Cond` | SMALLINT |  |  |  |
| 20 | `Flag_Z0_Input` | SMALLINT |  |  |  |
| 21 | `R0_R1` | FLOAT |  |  |  |
| 22 | `X0_X1` | FLOAT |  |  |  |
| 23 | `r0` | FLOAT |  |  |  |
| 24 | `x0` | FLOAT |  |  |  |
| 25 | `c0` | FLOAT |  |  |  |
| 26 | `rR` | FLOAT |  |  |  |
| 27 | `xR` | FLOAT |  |  |  |
| 28 | `cR` | FLOAT |  |  |  |
| 29 | `LineInfo` | CHAR(50) |  |  |  |
| 30 | `Flag_Vart` | SMALLINT |  |  |  |
| 31 | `q` | FLOAT |  |  |  |
| 32 | `d` | FLOAT |  |  |  |
| 33 | `da` | FLOAT |  |  |  |
| 34 | `Umax` | FLOAT |  |  |  |
| 35 | `Flag_Ground` | SMALLINT |  |  |  |
| 36 | `q0` | FLOAT |  |  |  |
| 37 | `Tend` | FLOAT |  |  |  |
| 38 | `I1s` | FLOAT |  |  |  |
| 39 | `Flag_Tend` | SMALLINT |  |  |  |
| 40 | `Ith` | FLOAT |  |  |  |
| 41 | `Ith1` | FLOAT |  |  |  |
| 42 | `Ith2` | FLOAT |  |  |  |
| 43 | `Ith3` | FLOAT |  |  |  |
| 44 | `fr` | FLOAT |  |  |  |
| 45 | `TempChar_ID` | INTEGER |  |  |  |
| 46 | `ElemLoading_ID` | INTEGER |  |  |  |
| 47 | `Flag_Har` | SMALLINT |  |  |  |
| 48 | `qr` | FLOAT |  |  |  |
| 49 | `ql` | FLOAT |  |  |  |
| 50 | `HarImp_ID` | INTEGER |  |  |  |
| 51 | `Flag_ESB` | SMALLINT |  |  |  |
| 52 | `Flag_Macro` | SMALLINT |  |  |  |
| 53 | `Macro_ID` | INTEGER |  |  |  |
| 54 | `Flag_Reliability` | SMALLINT |  |  |  |
| 55 | `Flag_SF1` | SMALLINT |  |  |  |
| 56 | `Flag_SF2` | SMALLINT |  |  |  |
| 57 | `LineType_ID` | INTEGER |  |  |  |
| 58 | `Overload_ID` | INTEGER |  |  |  |
| 59 | `V_S` | FLOAT |  |  |  |
| 60 | `Flag_ZU` | SMALLINT |  |  |  |
| 61 | `Flag_ZUP` | SMALLINT |  |  |  |
| 62 | `T_ZU` | FLOAT |  |  |  |
| 63 | `fIk` | FLOAT |  |  |  |
| 64 | `LineTemp_ID` | INTEGER |  |  |  |
| 65 | `Flag_Lf` | SMALLINT |  |  |  |

Example row (non-empty fields only):

```
Element_ID=5, Variant_ID=1, Flag_Variant=1, Flag_LineTyp=2, Un=11.0, l=2.0, ParSys=1.0, r=0.3, x=0.35, fn=50.0, Flag_Cond=1, Flag_Z0_Input=1, Flag_Vart=1, d=50.0, da=50.0, Ith=0.12, fr=1.0, Flag_Har=1, qr=1.0, Flag_ESB=1, Flag_ZUP=3, fIk=1.0, Flag_Lf=1
```

### Load  (94 columns, 4 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `Element_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `Flag_Typified` | SMALLINT |  |  |  |
| 4 | `Flag_Load` | SMALLINT |  |  |  |
| 5 | `Flag_LoadType` | SMALLINT |  |  |  |
| 6 | `Flag_Lf` | SMALLINT |  |  |  |
| 7 | `P` | FLOAT |  |  |  |
| 8 | `Q` | FLOAT |  |  |  |
| 9 | `u` | FLOAT |  |  |  |
| 10 | `Ul` | FLOAT |  |  |  |
| 11 | `Flag_Voltage` | SMALLINT |  |  |  |
| 12 | `cosphi` | FLOAT |  |  |  |
| 13 | `S` | FLOAT |  |  |  |
| 14 | `I` | FLOAT |  |  |  |
| 15 | `Eapcon` | FLOAT |  |  |  |
| 16 | `Erpcon` | FLOAT |  |  |  |
| 17 | `P12` | FLOAT |  |  |  |
| 18 | `Q12` | FLOAT |  |  |  |
| 19 | `P23` | FLOAT |  |  |  |
| 20 | `Q23` | FLOAT |  |  |  |
| 21 | `P31` | FLOAT |  |  |  |
| 22 | `Q31` | FLOAT |  |  |  |
| 23 | `P1` | FLOAT |  |  |  |
| 24 | `Q1` | FLOAT |  |  |  |
| 25 | `P2` | FLOAT |  |  |  |
| 26 | `Q2` | FLOAT |  |  |  |
| 27 | `P3` | FLOAT |  |  |  |
| 28 | `Q3` | FLOAT |  |  |  |
| 29 | `E` | FLOAT |  |  |  |
| 30 | `t` | FLOAT |  |  |  |
| 31 | `Eap` | FLOAT |  |  |  |
| 32 | `Erp` | FLOAT |  |  |  |
| 33 | `EPmax` | FLOAT |  |  |  |
| 34 | `Ebase` | FLOAT |  |  |  |
| 35 | `fP` | FLOAT |  |  |  |
| 36 | `fQ` | FLOAT |  |  |  |
| 37 | `fS` | FLOAT |  |  |  |
| 38 | `fI` | FLOAT |  |  |  |
| 39 | `fEapcon` | FLOAT |  |  |  |
| 40 | `fErpcon` | FLOAT |  |  |  |
| 41 | `fE` | FLOAT |  |  |  |
| 42 | `fEap` | FLOAT |  |  |  |
| 43 | `fErp` | FLOAT |  |  |  |
| 44 | `Flag_Macro` | SMALLINT |  |  |  |
| 45 | `Macro_ID` | INTEGER |  |  |  |
| 46 | `DayOpSer_ID` | INTEGER |  |  |  |
| 47 | `YearOpSer_ID` | INTEGER |  |  |  |
| 48 | `WeekOpSer_ID` | INTEGER |  |  |  |
| 49 | `IncrSer_ID` | INTEGER |  |  |  |
| 50 | `Gang_ID` | INTEGER |  |  |  |
| 51 | `Flag_LA` | SMALLINT |  |  |  |
| 52 | `Flag_Z0_Input` | SMALLINT |  |  |  |
| 53 | `Z0_Z1` | FLOAT |  |  |  |
| 54 | `R0_X0` | FLOAT |  |  |  |
| 55 | `R0` | FLOAT |  |  |  |
| 56 | `X0` | FLOAT |  |  |  |
| 57 | `Stp_ID` | INTEGER |  |  |  |
| 58 | `Pneg` | FLOAT |  |  |  |
| 59 | `Qneg` | FLOAT |  |  |  |
| 60 | `Load_ID` | INTEGER |  |  |  |
| 61 | `Flag_Measure` | SMALLINT |  |  |  |
| 62 | `P_max` | FLOAT |  |  |  |
| 63 | `P_min` | FLOAT |  |  |  |
| 64 | `Imax` | FLOAT |  |  |  |
| 65 | `I_min` | FLOAT |  |  |  |
| 66 | `cos_phi_imax` | FLOAT |  |  |  |
| 67 | `cos_phi_imin` | FLOAT |  |  |  |
| 68 | `du_min` | FLOAT |  |  |  |
| 69 | `du_max` | FLOAT |  |  |  |
| 70 | `TransformerTap_ID` | INTEGER |  |  |  |
| 71 | `Flag_Har` | SMALLINT |  |  |  |
| 72 | `qr` | FLOAT |  |  |  |
| 73 | `ql` | FLOAT |  |  |  |
| 74 | `HarImp_ID` | INTEGER |  |  |  |
| 75 | `HarVolt_ID` | INTEGER |  |  |  |
| 76 | `HarCur_ID` | INTEGER |  |  |  |
| 77 | `Flag_I` | SMALLINT |  |  |  |
| 78 | `Ireg` | FLOAT |  |  |  |
| 79 | `pk` | FLOAT |  |  |  |
| 80 | `SatChar_ID` | INTEGER |  |  |  |
| 81 | `ResFlux1` | FLOAT |  |  |  |
| 82 | `ResFlux2` | FLOAT |  |  |  |
| 83 | `ResFlux3` | FLOAT |  |  |  |
| 84 | `Flag_LP` | SMALLINT |  |  |  |
| 85 | `CustCnt` | INTEGER |  |  |  |
| 86 | `S_Inst` | FLOAT |  |  |  |
| 87 | `S_Peak` | FLOAT |  |  |  |
| 88 | `Flag_ShdU` | SMALLINT |  |  |  |
| 89 | `Flag_ShdP` | SMALLINT |  |  |  |
| 90 | `tShd` | FLOAT |  |  |  |
| 91 | `Typ_ID` | INTEGER |  |  |  |
| 92 | `Mpl_ID` | INTEGER |  |  |  |
| 93 | `Flag_Z0` | SMALLINT |  |  |  |

Example row (non-empty fields only):

```
Element_ID=8, Variant_ID=1, Flag_Variant=1, Flag_Typified=1, Flag_Load=1, Flag_LoadType=2, Flag_Lf=1, P=0.8, Q=0.3, u=100.0, Flag_Voltage=1, cosphi=1.0, fP=1.0, fQ=1.0, fS=1.0, fI=1.0, fEapcon=1.0, fErpcon=1.0, fE=1.0, fEap=1.0, fErp=1.0, Flag_Z0_Input=1, Flag_Measure=1, cos_phi_imax=0.95, cos_phi_imin=0.75, Flag_Har=1, qr=1.0, Flag_I=1, Flag_LP=3, CustCnt=1, Flag_Z0=1
```

### TwoWindingTransformer  (111 columns, 2 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `Element_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `Typ_ID` | INTEGER |  |  |  |
| 4 | `Flag_Typ_ID` | SMALLINT |  |  |  |
| 5 | `Un1` | FLOAT |  |  |  |
| 6 | `Un2` | FLOAT |  |  |  |
| 7 | `Sn` | FLOAT |  |  |  |
| 8 | `Smax` | FLOAT |  |  |  |
| 9 | `Smax1` | FLOAT |  |  |  |
| 10 | `Smax2` | FLOAT |  |  |  |
| 11 | `Smax3` | FLOAT |  |  |  |
| 12 | `ElemLoading_ID` | INTEGER |  |  |  |
| 13 | `uk` | FLOAT |  |  |  |
| 14 | `Flag_ur` | SMALLINT |  |  |  |
| 15 | `ur` | FLOAT |  |  |  |
| 16 | `Pvlk` | FLOAT |  |  |  |
| 17 | `Vfe` | FLOAT |  |  |  |
| 18 | `i0` | FLOAT |  |  |  |
| 19 | `VecGrp` | SMALLINT |  |  |  |
| 20 | `AddRotate` | FLOAT |  |  |  |
| 21 | `Flag_Boost` | SMALLINT |  |  |  |
| 22 | `uk_Ct` | FLOAT |  |  |  |
| 23 | `ur_Ct` | FLOAT |  |  |  |
| 24 | `Flag_Lf` | SMALLINT |  |  |  |
| 25 | `Flag_Macro` | SMALLINT |  |  |  |
| 26 | `Macro_ID` | INTEGER |  |  |  |
| 27 | `Flag_Z0_Input` | SMALLINT |  |  |  |
| 28 | `C01` | FLOAT |  |  |  |
| 29 | `C02` | FLOAT |  |  |  |
| 30 | `Z0_Z1` | FLOAT |  |  |  |
| 31 | `R0_X0` | FLOAT |  |  |  |
| 32 | `R0` | FLOAT |  |  |  |
| 33 | `X0` | FLOAT |  |  |  |
| 34 | `X0_X1` | FLOAT |  |  |  |
| 35 | `R0_R1` | FLOAT |  |  |  |
| 36 | `ZABNL` | FLOAT |  |  |  |
| 37 | `ZBANL` | FLOAT |  |  |  |
| 38 | `ZABSC` | FLOAT |  |  |  |
| 39 | `Stp_ID1` | INTEGER |  |  |  |
| 40 | `Stp_ID2` | INTEGER |  |  |  |
| 41 | `Flag_ConNode` | SMALLINT |  |  |  |
| 42 | `Flag_TapInput` | SMALLINT |  |  |  |
| 43 | `TransformerTap_ID` | INTEGER |  |  |  |
| 44 | `rohl` | FLOAT |  |  |  |
| 45 | `rohm` | FLOAT |  |  |  |
| 46 | `rohu` | FLOAT |  |  |  |
| 47 | `alpha` | FLOAT |  |  |  |
| 48 | `ukr` | FLOAT |  |  |  |
| 49 | `phi` | FLOAT |  |  |  |
| 50 | `ukl` | FLOAT |  |  |  |
| 51 | `uku` | FLOAT |  |  |  |
| 52 | `Flag_Tap` | SMALLINT |  |  |  |
| 53 | `roh` | FLOAT |  |  |  |
| 54 | `roh1` | FLOAT |  |  |  |
| 55 | `roh2` | FLOAT |  |  |  |
| 56 | `roh3` | FLOAT |  |  |  |
| 57 | `Ctrl_OpSer_ID` | INTEGER |  |  |  |
| 58 | `Ctrl_OpPnt_ID` | INTEGER |  |  |  |
| 59 | `Flag_roh` | SMALLINT |  |  |  |
| 60 | `Flag_Ph` | SMALLINT |  |  |  |
| 61 | `Flag_Step` | SMALLINT |  |  |  |
| 62 | `Node_ID` | INTEGER |  |  |  |
| 63 | `ull` | FLOAT |  |  |  |
| 64 | `uul` | FLOAT |  |  |  |
| 65 | `Proh` | FLOAT |  |  |  |
| 66 | `Proh2` | FLOAT |  |  |  |
| 67 | `Qroh` | FLOAT |  |  |  |
| 68 | `Qroh2` | FLOAT |  |  |  |
| 69 | `TransformerCon_ID` | INTEGER |  |  |  |
| 70 | `CompImp_ID` | INTEGER |  |  |  |
| 71 | `Flag_CompNode` | SMALLINT |  |  |  |
| 72 | `CtrlRange_ID` | INTEGER |  |  |  |
| 73 | `MasterElm_ID` | INTEGER |  |  |  |
| 74 | `Flag_Har` | SMALLINT |  |  |  |
| 75 | `qr` | FLOAT |  |  |  |
| 76 | `ql` | FLOAT |  |  |  |
| 77 | `HarImp_ID` | INTEGER |  |  |  |
| 78 | `SatChar_ID` | INTEGER |  |  |  |
| 79 | `ResFlux1` | FLOAT |  |  |  |
| 80 | `ResFlux2` | FLOAT |  |  |  |
| 81 | `ResFlux3` | FLOAT |  |  |  |
| 82 | `tctrl_dyn` | FLOAT |  |  |  |
| 83 | `cosphiG` | FLOAT |  |  |  |
| 84 | `Flag_Reliability` | SMALLINT |  |  |  |
| 85 | `Flag_SF1` | SMALLINT |  |  |  |
| 86 | `Flag_SF2` | SMALLINT |  |  |  |
| 87 | `TransformerType_ID` | INTEGER |  |  |  |
| 88 | `Overload_ID` | INTEGER |  |  |  |
| 89 | `V_S` | FLOAT |  |  |  |
| 90 | `Flag_ZU` | SMALLINT |  |  |  |
| 91 | `Flag_ZUP` | SMALLINT |  |  |  |
| 92 | `T_ZU` | FLOAT |  |  |  |
| 93 | `Flag_Inrush` | SMALLINT |  |  |  |
| 94 | `U_inrush` | FLOAT |  |  |  |
| 95 | `I_inrush` | FLOAT |  |  |  |
| 96 | `t_inrush` | FLOAT |  |  |  |
| 97 | `Ipeak` | FLOAT |  |  |  |
| 98 | `Tau` | FLOAT |  |  |  |
| 99 | `InCur_ID` | INTEGER |  |  |  |
| 100 | `Flag_Damage` | SMALLINT |  |  |  |
| 101 | `c` | FLOAT |  |  |  |
| 102 | `UnG` | FLOAT |  |  |  |
| 103 | `UnN` | FLOAT |  |  |  |
| 104 | `UGmax` | FLOAT |  |  |  |
| 105 | `Flag_Side` | SMALLINT |  |  |  |
| 106 | `Flag_Ct` | SMALLINT |  |  |  |
| 107 | `StpCt_ID` | INTEGER |  |  |  |
| 108 | `RX_ZABNL` | FLOAT |  |  |  |
| 109 | `RX_ZBANL` | FLOAT |  |  |  |
| 110 | `RX_ZABSC` | FLOAT |  |  |  |

Example row (non-empty fields only):

```
Element_ID=1, Variant_ID=1, Flag_Variant=-1, Un1=33.0, Un2=33.0, uk=8.0, Flag_ur=1, VecGrp=6, uk_Ct=16.0, Flag_Lf=1, Flag_Z0_Input=1, Flag_ConNode=1, Flag_roh=1, Flag_Ph=8, ull=98.0, uul=103.0, Flag_CompNode=2, Flag_Har=1, qr=1.0, tctrl_dyn=300.0, cosphiG=0.9, Flag_ZUP=3, I_inrush=0.1, t_inrush=0.05, Ipeak=0.1, Tau=0.05, Flag_Damage=1, c=1.1, UGmax=100.0, Flag_Side=1
```

### Terminal  (14 columns, 22 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `Terminal_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `Element_ID` | INTEGER |  |  |  |
| 4 | `Node_ID` | INTEGER |  |  |  |
| 5 | `TerminalNo` | SMALLINT |  |  |  |
| 6 | `Flag_State` | SMALLINT |  |  |  |
| 7 | `Flag_Switch` | SMALLINT |  |  |  |
| 8 | `Flag_Terminal` | SMALLINT |  |  |  |
| 9 | `Flag_Obs` | SMALLINT |  |  |  |
| 10 | `Flag_Cur` | SMALLINT |  |  |  |
| 11 | `Ir` | FLOAT |  |  |  |
| 12 | `Ik2` | FLOAT |  |  |  |
| 13 | `Report_No` | INTEGER |  |  |  |

Example row (non-empty fields only):

```
Terminal_ID=1, Variant_ID=1, Flag_Variant=-1, Element_ID=1, Node_ID=1, TerminalNo=1, Flag_State=1, Flag_Terminal=7, Report_No=1
```

### Element  (30 columns, 14 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `Element_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `Type` | CHAR(50) |  |  |  |
| 4 | `Flag_Input` | INTEGER |  |  |  |
| 5 | `Flag_Calc` | INTEGER |  |  |  |
| 6 | `Flag_Private` | INTEGER |  |  |  |
| 7 | `Flag_State` | SMALLINT |  |  |  |
| 8 | `Name` | CHAR(50) |  |  |  |
| 9 | `ShortName` | CHAR(8) |  |  |  |
| 10 | `Description` | CHAR(50) |  |  |  |
| 11 | `VoltLevel_ID` | INTEGER |  |  |  |
| 12 | `Group_ID` | INTEGER |  |  |  |
| 13 | `Zone_ID` | INTEGER |  |  |  |
| 14 | `EcoStation_ID` | INTEGER |  |  |  |
| 15 | `EcoField_ID` | INTEGER |  |  |  |
| 16 | `Ti` | DATE |  |  |  |
| 17 | `Ts` | DATE |  |  |  |
| 18 | `TextVal` | TEXT |  |  |  |
| 19 | `ci` | FLOAT |  |  |  |
| 20 | `Cs` | FLOAT |  |  |  |
| 21 | `cm` | FLOAT |  |  |  |
| 22 | `coo` | FLOAT |  |  |  |
| 23 | `Tl` | FLOAT |  |  |  |
| 24 | `Theta_i` | FLOAT |  |  |  |
| 25 | `Theta_u` | FLOAT |  |  |  |
| 26 | `fCe` | FLOAT |  |  |  |
| 27 | `fAkt` | FLOAT |  |  |  |
| 28 | `Metered` | SMALLINT |  |  |  |
| 29 | `Report_No` | INTEGER |  |  |  |

Example row (non-empty fields only):

```
Element_ID=1, Variant_ID=1, Flag_Variant=-1, Type='TwoWindingTransformer', Flag_State=1, Name='2T1', ShortName='2T1', VoltLevel_ID=1, Group_ID=1, fCe=1.0, fAkt=1.0, Report_No=1
```

### VoltageLevel  (87 columns, 2 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `VoltLevel_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `Name` | CHAR(50) |  |  |  |
| 4 | `ShortName` | CHAR(8) |  |  |  |
| 5 | `Flag_Volt` | SMALLINT |  |  |  |
| 6 | `Un` | FLOAT |  |  |  |
| 7 | `Uop` | FLOAT |  |  |  |
| 8 | `f` | FLOAT |  |  |  |
| 9 | `Temp_Line` | FLOAT |  |  |  |
| 10 | `Temp_Cable` | FLOAT |  |  |  |
| 11 | `AmbTemp_Line` | FLOAT |  |  |  |
| 12 | `AmbTemp_Cable` | FLOAT |  |  |  |
| 13 | `TempTrf` | FLOAT |  |  |  |
| 14 | `Flag_LimitRes` | SMALLINT |  |  |  |
| 15 | `ull` | FLOAT |  |  |  |
| 16 | `uul` | FLOAT |  |  |  |
| 17 | `I_In_Elem` | FLOAT |  |  |  |
| 18 | `I_In_Line` | FLOAT |  |  |  |
| 19 | `Flag_Sc` | SMALLINT |  |  |  |
| 20 | `AddFaultData_ID` | INTEGER |  |  |  |
| 21 | `Flag_CurStp` | SMALLINT |  |  |  |
| 22 | `ts` | FLOAT |  |  |  |
| 23 | `Flag_Toleranz` | SMALLINT |  |  |  |
| 24 | `Flag_Usc` | SMALLINT |  |  |  |
| 25 | `c` | FLOAT |  |  |  |
| 26 | `Uk` | FLOAT |  |  |  |
| 27 | `u_ansi` | FLOAT |  |  |  |
| 28 | `Ikmax` | FLOAT |  |  |  |
| 29 | `tkr` | FLOAT |  |  |  |
| 30 | `Ipmax` | FLOAT |  |  |  |
| 31 | `Iamax` | FLOAT |  |  |  |
| 32 | `Flag_CompPower` | SMALLINT |  |  |  |
| 33 | `CosPhi_ind` | FLOAT |  |  |  |
| 34 | `CosPhi_kap` | FLOAT |  |  |  |
| 35 | `Flag_Balance` | SMALLINT |  |  |  |
| 36 | `HarDistLimit_ID` | INTEGER |  |  |  |
| 37 | `hmax_THD` | SMALLINT |  |  |  |
| 38 | `fRD` | FLOAT |  |  |  |
| 39 | `Flag_Arc_I` | SMALLINT |  |  |  |
| 40 | `I_Fkt_R` | FLOAT |  |  |  |
| 41 | `I_R` | FLOAT |  |  |  |
| 42 | `I_R_X` | FLOAT |  |  |  |
| 43 | `Flag_Arc_M` | SMALLINT |  |  |  |
| 44 | `M_Fkt_R` | FLOAT |  |  |  |
| 45 | `M_R` | FLOAT |  |  |  |
| 46 | `M_R_X` | FLOAT |  |  |  |
| 47 | `Flag_Arc_K` | SMALLINT |  |  |  |
| 48 | `K_Fkt_R` | FLOAT |  |  |  |
| 49 | `K_R` | FLOAT |  |  |  |
| 50 | `K_R_X` | FLOAT |  |  |  |
| 51 | `Flag_Arc_P` | SMALLINT |  |  |  |
| 52 | `P_Fkt_R` | FLOAT |  |  |  |
| 53 | `P_R` | FLOAT |  |  |  |
| 54 | `P_R_X` | FLOAT |  |  |  |
| 55 | `Flag_Arc_MHO` | SMALLINT |  |  |  |
| 56 | `MHO_Fkt_R` | FLOAT |  |  |  |
| 57 | `MHO_R` | FLOAT |  |  |  |
| 58 | `MHO_R_X` | FLOAT |  |  |  |
| 59 | `Flag_Arc_Comb` | SMALLINT |  |  |  |
| 60 | `Comb_Fkt_R` | FLOAT |  |  |  |
| 61 | `Comb_R` | FLOAT |  |  |  |
| 62 | `Comb_R_X` | FLOAT |  |  |  |
| 63 | `LF_Safety_I` | FLOAT |  |  |  |
| 64 | `LF_Safety_Phi` | FLOAT |  |  |  |
| 65 | `LF_Safety_Z` | FLOAT |  |  |  |
| 66 | `Udgr` | FLOAT |  |  |  |
| 67 | `Flag_Reliability` | SMALLINT |  |  |  |
| 68 | `SwitchBay1_ID` | INTEGER |  |  |  |
| 69 | `SwitchBay2_ID` | INTEGER |  |  |  |
| 70 | `BusbarType_ID` | INTEGER |  |  |  |
| 71 | `LineType_ID` | INTEGER |  |  |  |
| 72 | `CableType_ID` | INTEGER |  |  |  |
| 73 | `TransformerType_ID` | INTEGER |  |  |  |
| 74 | `SupplyType_ID` | INTEGER |  |  |  |
| 75 | `DCInfeederType_ID` | INTEGER |  |  |  |
| 76 | `LoadDurCurve_ID` | INTEGER |  |  |  |
| 77 | `Flag_LP` | SMALLINT |  |  |  |
| 78 | `Flag_DCInfeeder` | SMALLINT |  |  |  |
| 79 | `cmin` | FLOAT |  |  |  |
| 80 | `cmax` | FLOAT |  |  |  |
| 81 | `Flag_RelElement` | SMALLINT |  |  |  |
| 82 | `SwitchDur_ID` | INTEGER |  |  |  |
| 83 | `dQ_rouch` | FLOAT |  |  |  |
| 84 | `dQ_fine` | FLOAT |  |  |  |
| 85 | `Flag_OptBr` | SMALLINT |  |  |  |
| 86 | `TempSun_Line` | FLOAT |  |  |  |

Example row (non-empty fields only):

```
VoltLevel_ID=1, Variant_ID=1, Flag_Variant=1, Name='33 kV', ShortName='133 kV', Flag_Volt=1, Un=33.0, f=50.0, Temp_Line=20.0, Temp_Cable=20.0, AmbTemp_Line=20.0, AmbTemp_Cable=20.0, TempTrf=20.0, ull=90.0, uul=110.0, I_In_Elem=100.0, I_In_Line=95.0, Flag_Sc=1, Flag_CurStp=1, ts=0.1, Flag_Toleranz=2, Flag_Usc=1, c=1.1, u_ansi=1.0, tkr=1.0, CosPhi_ind=0.95, CosPhi_kap=-0.95, Flag_Balance=1, fRD=50.0, I_Fkt_R=1.5, I_R=4.0, I_R_X=0.25, M_Fkt_R=1.5, M_R=4.0, M_R_X=0.25, K_Fkt_R=1.5, K_R=4.0, K_R_X=0.25, P_Fkt_R=1.5, P_R=4.0, P_R_X=0.25, MHO_Fkt_R=1.5, MHO_R=4.0, MHO_R_X=0.25, Comb_Fkt_R=1.5, Comb_R=4.0, Comb_R_X=0.25, LF_Safety_I=20.0, LF_Safety_Phi=5.0, LF_Safety_Z=20.0, Flag_LP=3, cmin=1.0, cmax=1.1, dQ_rouch=10.0, dQ_fine=2.0, Flag_OptBr=1, TempSun_Line=20.0
```

### GraphicNode  (20 columns, 10 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `GraphicNode_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `GraphicLayer_ID` | INTEGER |  |  |  |
| 4 | `GraphicType_ID` | INTEGER |  |  |  |
| 5 | `GraphicText_ID1` | INTEGER |  |  |  |
| 6 | `GraphicText_ID2` | INTEGER |  |  |  |
| 7 | `Node_ID` | INTEGER |  |  |  |
| 8 | `FrgndColor` | INTEGER |  |  |  |
| 9 | `BkgndColor` | INTEGER |  |  |  |
| 10 | `PenStyle` | SMALLINT |  |  |  |
| 11 | `PenWidth` | FLOAT |  |  |  |
| 12 | `NodeSize` | FLOAT |  |  |  |
| 13 | `NodeStartX` | FLOAT |  |  |  |
| 14 | `NodeStartY` | FLOAT |  |  |  |
| 15 | `NodeEndX` | FLOAT |  |  |  |
| 16 | `NodeEndY` | FLOAT |  |  |  |
| 17 | `SymType` | SMALLINT |  |  |  |
| 18 | `Flag` | INTEGER |  |  |  |
| 19 | `GraphicArea_ID` | INTEGER |  |  |  |

Example row (non-empty fields only):

```
GraphicNode_ID=1, Variant_ID=1, Flag_Variant=1, GraphicLayer_ID=1, GraphicType_ID=1, GraphicText_ID1=1, Node_ID=1, BkgndColor=-1, PenWidth=2.0, NodeSize=0.1, NodeStartX=0.12000000000000001, NodeStartY=0.2125000000000002, NodeEndX=0.12000000000000001, NodeEndY=0.1700000000000002, SymType=3, GraphicArea_ID=1
```

### GraphicText  (18 columns, 46 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `GraphicText_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `GraphicLayer_ID` | INTEGER |  |  |  |
| 4 | `Font` | CHAR(20) |  |  |  |
| 5 | `FontStyle` | SMALLINT |  |  |  |
| 6 | `FontSize` | FLOAT |  |  |  |
| 7 | `TextAlign` | SMALLINT |  |  |  |
| 8 | `TextOrient` | SMALLINT |  |  |  |
| 9 | `TextColor` | INTEGER |  |  |  |
| 10 | `Visible` | SMALLINT |  |  |  |
| 11 | `AdjustAngle` | SMALLINT |  |  |  |
| 12 | `Angle` | FLOAT |  |  |  |
| 13 | `Pos1` | FLOAT |  |  |  |
| 14 | `Pos2` | FLOAT |  |  |  |
| 15 | `Flag` | INTEGER |  |  |  |
| 16 | `RowTextNo` | SMALLINT |  |  |  |
| 17 | `AngleTermNo` | SMALLINT |  |  |  |

Example row (non-empty fields only):

```
GraphicText_ID=1, Variant_ID=1, Flag_Variant=1, GraphicLayer_ID=1, Font='Arial', FontStyle=16, FontSize=9.33, Visible=1, AdjustAngle=1, Pos1=-0.0025
```

### CalcParameter  (228 columns, 1 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `CalcParameter_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `LC_StartDate` | DATE |  |  |  |
| 4 | `Flag_XVU` | SMALLINT |  |  |  |
| 5 | `Flag_UseOpSer` | SMALLINT |  |  |  |
| 6 | `Op_ID` | INTEGER |  |  |  |
| 7 | `Flag_UseTimeSer` | SMALLINT |  |  |  |
| 8 | `Flag_UseLA` | SMALLINT |  |  |  |
| 9 | `Flag_LA` | SMALLINT |  |  |  |
| 10 | `EcoTl` | INTEGER |  |  |  |
| 11 | `Flag_UseIncSer` | SMALLINT |  |  |  |
| 12 | `Flag_OptBrLF` | SMALLINT |  |  |  |
| 13 | `EcoTt` | INTEGER |  |  |  |
| 14 | `Flag_ReallocPower` | SMALLINT |  |  |  |
| 15 | `Flag_UseScenario` | SMALLINT |  |  |  |
| 16 | `Scenario_ID` | INTEGER |  |  |  |
| 17 | `Flag_Scenario` | SMALLINT |  |  |  |
| 18 | `Flag_BCC` | SMALLINT |  |  |  |
| 19 | `f` | FLOAT |  |  |  |
| 20 | `T_SUE` | FLOAT |  |  |  |
| 21 | `T_U` | FLOAT |  |  |  |
| 22 | `Flag_LFZ0` | SMALLINT |  |  |  |
| 23 | `Lock_R0` | FLOAT |  |  |  |
| 24 | `Lock_X0` | FLOAT |  |  |  |
| 25 | `Flag_LFmet` | SMALLINT |  |  |  |
| 26 | `Flag_LfStartVal` | SMALLINT |  |  |  |
| 27 | `Flag_XSU` | SMALLINT |  |  |  |
| 28 | `Flag_ABW` | SMALLINT |  |  |  |
| 29 | `Flag_ZKR` | SMALLINT |  |  |  |
| 30 | `Flag_BIM` | SMALLINT |  |  |  |
| 31 | `Flag_XME` | SMALLINT |  |  |  |
| 32 | `ITmax` | INTEGER |  |  |  |
| 33 | `Rmin` | FLOAT |  |  |  |
| 34 | `T_CM` | FLOAT |  |  |  |
| 35 | `T_SV` | FLOAT |  |  |  |
| 36 | `PNB` | FLOAT |  |  |  |
| 37 | `VLB` | FLOAT |  |  |  |
| 38 | `VDN` | FLOAT |  |  |  |
| 39 | `Flag_TraReg` | SMALLINT |  |  |  |
| 40 | `Flag_ShuntReg` | SMALLINT |  |  |  |
| 41 | `Flag_GenReg` | SMALLINT |  |  |  |
| 42 | `Flag_Unit` | SMALLINT |  |  |  |
| 43 | `Flag_RedistP` | SMALLINT |  |  |  |
| 44 | `Flag_PhiUlf` | SMALLINT |  |  |  |
| 45 | `IncrStartDate` | DATE |  |  |  |
| 46 | `IncrEndDate` | DATE |  |  |  |
| 47 | `LoadDataDate` | DATE |  |  |  |
| 48 | `EcoTt_ts` | DATE |  |  |  |
| 49 | `Flag_LDECO` | SMALLINT |  |  |  |
| 50 | `EcoP` | FLOAT |  |  |  |
| 51 | `EcoInflation` | FLOAT |  |  |  |
| 52 | `EcoCe` | FLOAT |  |  |  |
| 53 | `OpSer_ID` | INTEGER |  |  |  |
| 54 | `IncrSer_ID` | INTEGER |  |  |  |
| 55 | `LC_StartTime` | FLOAT |  |  |  |
| 56 | `LC_Duration` | FLOAT |  |  |  |
| 57 | `LC_TimeStep` | FLOAT |  |  |  |
| 58 | `FLAG_IND` | SMALLINT |  |  |  |
| 59 | `Flag_XCM` | SMALLINT |  |  |  |
| 60 | `ITLF` | INTEGER |  |  |  |
| 61 | `ITOP1` | FLOAT |  |  |  |
| 62 | `ITOP2` | FLOAT |  |  |  |
| 63 | `ITcon` | FLOAT |  |  |  |
| 64 | `f1` | FLOAT |  |  |  |
| 65 | `f2` | FLOAT |  |  |  |
| 66 | `f3` | FLOAT |  |  |  |
| 67 | `f4` | FLOAT |  |  |  |
| 68 | `c1` | FLOAT |  |  |  |
| 69 | `c2` | FLOAT |  |  |  |
| 70 | `c3` | FLOAT |  |  |  |
| 71 | `Flag_PreL` | SMALLINT |  |  |  |
| 72 | `Flag_ScType` | SMALLINT |  |  |  |
| 73 | `Flag_SCM` | SMALLINT |  |  |  |
| 74 | `Temp_Dim` | FLOAT |  |  |  |
| 75 | `AddFaultData_ID` | INTEGER |  |  |  |
| 76 | `Flag_SCC` | SMALLINT |  |  |  |
| 77 | `tmin` | FLOAT |  |  |  |
| 78 | `Flag_Ansi_Method` | SMALLINT |  |  |  |
| 79 | `Flag_Ansi_NACD` | SMALLINT |  |  |  |
| 80 | `fl2` | FLOAT |  |  |  |
| 81 | `Flag_UseArc` | SMALLINT |  |  |  |
| 82 | `Flag_CalcRX` | SMALLINT |  |  |  |
| 83 | `Flag_Converter` | SMALLINT |  |  |  |
| 84 | `Flag_VoltSupport` | SMALLINT |  |  |  |
| 85 | `Flag_SCContribution` | SMALLINT |  |  |  |
| 86 | `Flag_Ansi_Trf` | SMALLINT |  |  |  |
| 87 | `Flag_Ansi_Line` | SMALLINT |  |  |  |
| 88 | `Flag_ScAsm` | SMALLINT |  |  |  |
| 89 | `Flag_DC` | SMALLINT |  |  |  |
| 90 | `Flag_Wind` | SMALLINT |  |  |  |
| 91 | `Flag_TrafoCorrection` | SMALLINT |  |  |  |
| 92 | `Flag_HW` | SMALLINT |  |  |  |
| 93 | `Flag_Arc_IEEE` | SMALLINT |  |  |  |
| 94 | `fD` | FLOAT |  |  |  |
| 95 | `Flag_HarFreq` | SMALLINT |  |  |  |
| 96 | `fs` | FLOAT |  |  |  |
| 97 | `fe` | FLOAT |  |  |  |
| 98 | `deltafmax` | FLOAT |  |  |  |
| 99 | `deltafmin` | FLOAT |  |  |  |
| 100 | `Flag_WE` | SMALLINT |  |  |  |
| 101 | `Flag_RN` | SMALLINT |  |  |  |
| 102 | `Flag_SwL` | SMALLINT |  |  |  |
| 103 | `Flag_HarLoad` | SMALLINT |  |  |  |
| 104 | `fRD` | FLOAT |  |  |  |
| 105 | `Flag_DDE` | SMALLINT |  |  |  |
| 106 | `Flag_Damage` | SMALLINT |  |  |  |
| 107 | `Flag_PreLD` | SMALLINT |  |  |  |
| 108 | `Flag_NType` | SMALLINT |  |  |  |
| 109 | `Sk2` | FLOAT |  |  |  |
| 110 | `sbdv` | FLOAT |  |  |  |
| 111 | `Flag_Area` | SMALLINT |  |  |  |
| 112 | `Flag_Ith` | SMALLINT |  |  |  |
| 113 | `Flag_I1s` | SMALLINT |  |  |  |
| 114 | `Flag_kfkt` | SMALLINT |  |  |  |
| 115 | `RC` | FLOAT |  |  |  |
| 116 | `XC` | FLOAT |  |  |  |
| 117 | `R0C` | FLOAT |  |  |  |
| 118 | `X0C` | FLOAT |  |  |  |
| 119 | `RL` | FLOAT |  |  |  |
| 120 | `XL` | FLOAT |  |  |  |
| 121 | `R0L` | FLOAT |  |  |  |
| 122 | `X0L` | FLOAT |  |  |  |
| 123 | `deltat1` | FLOAT |  |  |  |
| 124 | `tend` | FLOAT |  |  |  |
| 125 | `deltat4` | FLOAT |  |  |  |
| 126 | `V_S` | FLOAT |  |  |  |
| 127 | `ZAI` | SMALLINT |  |  |  |
| 128 | `ModelName` | CHAR(20) |  |  |  |
| 129 | `Flag_Syn_PM` | SMALLINT |  |  |  |
| 130 | `Flag_DynReference` | SMALLINT |  |  |  |
| 131 | `Currency_ID` | INTEGER |  |  |  |
| 132 | `Flag_X1P` | SMALLINT |  |  |  |
| 133 | `Flag_ProtDyn` | SMALLINT |  |  |  |
| 134 | `Flag_DynRes` | SMALLINT |  |  |  |
| 135 | `Flag_ZLZ` | SMALLINT |  |  |  |
| 136 | `ZQI` | FLOAT |  |  |  |
| 137 | `Rmax` | FLOAT |  |  |  |
| 138 | `Xmin` | FLOAT |  |  |  |
| 139 | `Flag_ZTS` | SMALLINT |  |  |  |
| 140 | `Flag_ZSH` | SMALLINT |  |  |  |
| 141 | `Flag_UseNSN` | SMALLINT |  |  |  |
| 142 | `Flag_DIType` | SMALLINT |  |  |  |
| 143 | `EVA_Method` | SMALLINT |  |  |  |
| 144 | `Zeta` | FLOAT |  |  |  |
| 145 | `ZetaChart` | FLOAT |  |  |  |
| 146 | `OmegaMin` | FLOAT |  |  |  |
| 147 | `OmegaMax` | FLOAT |  |  |  |
| 148 | `SigmaMin` | FLOAT |  |  |  |
| 149 | `SigmaMax` | FLOAT |  |  |  |
| 150 | `SigmaStart` | FLOAT |  |  |  |
| 151 | `U_ABW` | FLOAT |  |  |  |
| 152 | `Flag_UZLF` | SMALLINT |  |  |  |
| 153 | `Flag_XDA` | SMALLINT |  |  |  |
| 154 | `Flag_XUS` | SMALLINT |  |  |  |
| 155 | `ts` | FLOAT |  |  |  |
| 156 | `tdelay` | FLOAT |  |  |  |
| 157 | `Zdivide` | FLOAT |  |  |  |
| 158 | `PT_Imin_p` | FLOAT |  |  |  |
| 159 | `deltat2` | FLOAT |  |  |  |
| 160 | `sbdv_prot` | SMALLINT |  |  |  |
| 161 | `fl1` | FLOAT |  |  |  |
| 162 | `Flag_DPE` | SMALLINT |  |  |  |
| 163 | `Flag_Step` | SMALLINT |  |  |  |
| 164 | `FLm` | FLOAT |  |  |  |
| 165 | `Flag_Strategie` | SMALLINT |  |  |  |
| 166 | `fD2P` | FLOAT |  |  |  |
| 167 | `Flag_fD3P` | SMALLINT |  |  |  |
| 168 | `Flag_Zprim` | SMALLINT |  |  |  |
| 169 | `Flag_Trafo` | SMALLINT |  |  |  |
| 170 | `Flag_FeedNode` | SMALLINT |  |  |  |
| 171 | `Flag_XUN` | SMALLINT |  |  |  |
| 172 | `Flag_QvtoQi` | SMALLINT |  |  |  |
| 173 | `t_st1` | FLOAT |  |  |  |
| 174 | `t_st2` | FLOAT |  |  |  |
| 175 | `t_st3` | FLOAT |  |  |  |
| 176 | `t_st4` | FLOAT |  |  |  |
| 177 | `t_st5` | FLOAT |  |  |  |
| 178 | `t_st6` | FLOAT |  |  |  |
| 179 | `ts_set` | FLOAT |  |  |  |
| 180 | `tstart` | FLOAT |  |  |  |
| 181 | `tend2` | FLOAT |  |  |  |
| 182 | `deltat3` | FLOAT |  |  |  |
| 183 | `tmax` | FLOAT |  |  |  |
| 184 | `EPM` | FLOAT |  |  |  |
| 185 | `Flag_DI` | SMALLINT |  |  |  |
| 186 | `Flag_LC_Incl` | SMALLINT |  |  |  |
| 187 | `Flag_XLV` | SMALLINT |  |  |  |
| 188 | `Flag_Det_ST` | SMALLINT |  |  |  |
| 189 | `Flag_XSV` | SMALLINT |  |  |  |
| 190 | `ZAA` | SMALLINT |  |  |  |
| 191 | `Flag_UsymElm` | SMALLINT |  |  |  |
| 192 | `Temp_Cond` | FLOAT |  |  |  |
| 193 | `ull` | FLOAT |  |  |  |
| 194 | `uul` | FLOAT |  |  |  |
| 195 | `PQ` | FLOAT |  |  |  |
| 196 | `DCE` | FLOAT |  |  |  |
| 197 | `DUE` | FLOAT |  |  |  |
| 198 | `c4` | FLOAT |  |  |  |
| 199 | `fl3` | FLOAT |  |  |  |
| 200 | `fl4` | FLOAT |  |  |  |
| 201 | `Rle1` | FLOAT |  |  |  |
| 202 | `Xle1` | FLOAT |  |  |  |
| 203 | `Ree1` | FLOAT |  |  |  |
| 204 | `Xee1` | FLOAT |  |  |  |
| 205 | `Rle2` | FLOAT |  |  |  |
| 206 | `Xle2` | FLOAT |  |  |  |
| 207 | `Ree2` | FLOAT |  |  |  |
| 208 | `Xee2` | FLOAT |  |  |  |
| 209 | `Rlsc2` | FLOAT |  |  |  |
| 210 | `Xlsc2` | FLOAT |  |  |  |
| 211 | `Rlsc3` | FLOAT |  |  |  |
| 212 | `Xlsc3` | FLOAT |  |  |  |
| 213 | `UnT` | FLOAT |  |  |  |
| 214 | `fzero` | FLOAT |  |  |  |
| 215 | `c` | FLOAT |  |  |  |
| 216 | `Imin` | FLOAT |  |  |  |
| 217 | `Imax` | FLOAT |  |  |  |
| 218 | `Uref` | FLOAT |  |  |  |
| 219 | `Xmax` | FLOAT |  |  |  |
| 220 | `Dgm_Zmax` | FLOAT |  |  |  |
| 221 | `Dgm_tmax` | FLOAT |  |  |  |
| 222 | `LC_Util` | FLOAT |  |  |  |
| 223 | `Set_RX_min` | FLOAT |  |  |  |
| 224 | `T_ME` | FLOAT |  |  |  |
| 225 | `T_DA` | FLOAT |  |  |  |
| 226 | `EcoTl_ts` | DATE |  |  |  |
| 227 | `LC_Util_Line` | FLOAT |  |  |  |

Example row (non-empty fields only):

```
CalcParameter_ID=1, Variant_ID=1, Flag_Variant=1, EcoTt=1, Flag_ReallocPower=1, Flag_Scenario=1, Flag_BCC=2, f=50.0, T_SUE=1.0, T_U=1.0, Flag_LFZ0=1, Lock_R0=10000.0, Flag_LFmet=2, Flag_ABW=1, Flag_ZKR=1, Flag_XME=1, ITmax=200, Rmin=80.0, T_CM=1.0, T_SV=1.0, PNB=0.001, VLB=0.01, VDN=0.01, EcoP=2.0, EcoInflation=1.0, EcoCe=0.3, LC_Duration=24.0, LC_TimeStep=0.25, FLAG_IND=1, Flag_XCM=2, ITLF=25, ITOP1=3.0, ITOP2=3.0, ITcon=50.0, f1=100.0, f2=1.0, f3=10.0, f4=10.0, c1=100.0, c2=1.0, c3=10.0, Flag_PreL=8, Flag_ScType=3, Temp_Dim=80.0, Flag_SCC=1, tmin=0.1, Flag_Ansi_Method=1, Flag_Ansi_NACD=1, Flag_UseArc=1, Flag_CalcRX=1, Flag_ScAsm=1, Flag_DC=1, Flag_Wind=1, Flag_TrafoCorrection=1, Flag_HW=1, Flag_Arc_IEEE=1, fD=1.0, Flag_HarFreq=2, fs=50.0, fe=2000.0, deltafmax=50.0, deltafmin=5.0, Flag_HarLoad=1, fRD=50.0, Flag_NType=1, Sk2=100.0, sbdv=9.0, Flag_kfkt=1, tend=1.0, deltat4=0.001, ZAI=1, Flag_Syn_PM=1, Flag_DynRes=1, Flag_ZLZ=1, ZQI=10.0, Flag_DIType=1, Zeta=-100.0, ZetaChart=5.0, OmegaMin=0.063, OmegaMax=6.283, SigmaMin=-2.0, SigmaMax=0.5, ts=0.15, tdelay=0.03, Zdivide=0.25, PT_Imin_p=5.0, deltat2=0.0005, sbdv_prot=10, fl1=1.0, Flag_Step=1, FLm=10.0, Flag_Strategie=1, fD2P=90.0, Flag_fD3P=2, Flag_Zprim=1, Flag_Trafo=1, Flag_XUN=1, Flag_QvtoQi=1, t_st1=0.25, t_st2=0.5, t_st3=0.75, t_st4=1.0, t_st5=1.0, t_st6=1.0, ts_set=0.25, tend2=60.0, deltat3=0.01, tmax=0.1, EPM=0.1, Flag_DI=1, Flag_LC_Incl=1, Flag_Det_ST=1, Flag_XSV=1, ZAA=1, Flag_UsymElm=1, Temp_Cond=20.0, ull=98.0, uul=103.0, PQ=1.2, DCE=0.003, DUE=0.003, c4=1.0, UnT=0.4, fzero=2.5, c=1.1, Imin=10.0, Imax=1.0, Uref=10.0, Xmax=25.0, Dgm_Zmax=5.0, Dgm_tmax=5.0, LC_Util=100.0, Set_RX_min=0.25, LC_Util_Line=95.0
```

### Infeeder  (123 columns, 1 rows here)

| # | Column | Type | Not null | Default | PK |
| ---: | --- | --- | :---: | --- | :---: |
| 0 | `Element_ID` | INTEGER | yes |  |  |
| 1 | `Variant_ID` | INTEGER | yes |  |  |
| 2 | `Flag_Variant` | SMALLINT |  |  |  |
| 3 | `Typ_ID` | INTEGER |  |  |  |
| 4 | `Flag_Typ_ID` | SMALLINT |  |  |  |
| 5 | `Flag_Typ` | SMALLINT |  |  |  |
| 6 | `R` | FLOAT |  |  |  |
| 7 | `X` | FLOAT |  |  |  |
| 8 | `Rmax` | FLOAT |  |  |  |
| 9 | `Xmax` | FLOAT |  |  |  |
| 10 | `Rmin` | FLOAT |  |  |  |
| 11 | `Xmin` | FLOAT |  |  |  |
| 12 | `Sk2` | FLOAT |  |  |  |
| 13 | `R_X` | FLOAT |  |  |  |
| 14 | `cact` | FLOAT |  |  |  |
| 15 | `Sk2max` | FLOAT |  |  |  |
| 16 | `R_Xmax` | FLOAT |  |  |  |
| 17 | `cmax` | FLOAT |  |  |  |
| 18 | `Sk2min` | FLOAT |  |  |  |
| 19 | `R_Xmin` | FLOAT |  |  |  |
| 20 | `cmin` | FLOAT |  |  |  |
| 21 | `xi` | FLOAT |  |  |  |
| 22 | `Flag_Z0` | SMALLINT |  |  |  |
| 23 | `Flag_Z0_Input` | SMALLINT |  |  |  |
| 24 | `Z0_Z1` | FLOAT |  |  |  |
| 25 | `R0_X0` | FLOAT |  |  |  |
| 26 | `Z0_Z1max` | FLOAT |  |  |  |
| 27 | `R0_X0max` | FLOAT |  |  |  |
| 28 | `Z0_Z1min` | FLOAT |  |  |  |
| 29 | `R0_X0min` | FLOAT |  |  |  |
| 30 | `R0` | FLOAT |  |  |  |
| 31 | `X0` | FLOAT |  |  |  |
| 32 | `R0max` | FLOAT |  |  |  |
| 33 | `X0max` | FLOAT |  |  |  |
| 34 | `R0min` | FLOAT |  |  |  |
| 35 | `X0min` | FLOAT |  |  |  |
| 36 | `Stp_ID` | INTEGER |  |  |  |
| 37 | `Flag_Lf` | SMALLINT |  |  |  |
| 38 | `Start_P` | FLOAT |  |  |  |
| 39 | `Start_Q` | FLOAT |  |  |  |
| 40 | `Flag_Macro` | SMALLINT |  |  |  |
| 41 | `Macro_ID` | INTEGER |  |  |  |
| 42 | `P` | FLOAT |  |  |  |
| 43 | `Q` | FLOAT |  |  |  |
| 44 | `fP` | FLOAT |  |  |  |
| 45 | `fQ` | FLOAT |  |  |  |
| 46 | `cosphi` | FLOAT |  |  |  |
| 47 | `S` | FLOAT |  |  |  |
| 48 | `fS` | FLOAT |  |  |  |
| 49 | `I` | FLOAT |  |  |  |
| 50 | `fI` | FLOAT |  |  |  |
| 51 | `phi` | FLOAT |  |  |  |
| 52 | `delta` | FLOAT |  |  |  |
| 53 | `u` | FLOAT |  |  |  |
| 54 | `delta1` | FLOAT |  |  |  |
| 55 | `delta2` | FLOAT |  |  |  |
| 56 | `delta3` | FLOAT |  |  |  |
| 57 | `u1` | FLOAT |  |  |  |
| 58 | `u2` | FLOAT |  |  |  |
| 59 | `u3` | FLOAT |  |  |  |
| 60 | `Ug` | FLOAT |  |  |  |
| 61 | `Rlf` | FLOAT |  |  |  |
| 62 | `Xlf` | FLOAT |  |  |  |
| 63 | `DayOpSer_ID` | INTEGER |  |  |  |
| 64 | `YearOpSer_ID` | INTEGER |  |  |  |
| 65 | `WeekOpSer_ID` | INTEGER |  |  |  |
| 66 | `IncrSer_ID` | INTEGER |  |  |  |
| 67 | `Flag_LfLimit` | SMALLINT |  |  |  |
| 68 | `ull` | FLOAT |  |  |  |
| 69 | `uul` | FLOAT |  |  |  |
| 70 | `Pmin` | FLOAT |  |  |  |
| 71 | `Pmax` | FLOAT |  |  |  |
| 72 | `Qmin` | FLOAT |  |  |  |
| 73 | `Qmax` | FLOAT |  |  |  |
| 74 | `cosphi_lim` | FLOAT |  |  |  |
| 75 | `PowerLimit_ID` | INTEGER |  |  |  |
| 76 | `Flag_ChkType` | SMALLINT |  |  |  |
| 77 | `Flag_LimitType` | SMALLINT |  |  |  |
| 78 | `Kr` | FLOAT |  |  |  |
| 79 | `Flag_Pctrl` | SMALLINT |  |  |  |
| 80 | `Qctrl_U_P_ID` | INTEGER |  |  |  |
| 81 | `Flag_Qctrl` | SMALLINT |  |  |  |
| 82 | `Qctrl_PF_U_ID` | INTEGER |  |  |  |
| 83 | `Qctrl_PF_P_ID` | INTEGER |  |  |  |
| 84 | `Qctrl_P_Q_ID` | INTEGER |  |  |  |
| 85 | `Qctrl_U_Q_ID` | INTEGER |  |  |  |
| 86 | `Qctrl_Pmin` | FLOAT |  |  |  |
| 87 | `Qctrl_Pmax` | FLOAT |  |  |  |
| 88 | `Qctrl_PF_Pmin` | FLOAT |  |  |  |
| 89 | `Qctrl_PF_Pmax` | FLOAT |  |  |  |
| 90 | `Qctrl_Qmin` | FLOAT |  |  |  |
| 91 | `Qctrl_Qmax` | FLOAT |  |  |  |
| 92 | `Qctrl_cosphi_c` | FLOAT |  |  |  |
| 93 | `Qctrl_cosphi` | FLOAT |  |  |  |
| 94 | `Qctrl_U1_c` | FLOAT |  |  |  |
| 95 | `Qctrl_U1` | FLOAT |  |  |  |
| 96 | `Qctrl_U2_c` | FLOAT |  |  |  |
| 97 | `Qctrl_U2` | FLOAT |  |  |  |
| 98 | `u_node` | FLOAT |  |  |  |
| 99 | `Node_ID` | INTEGER |  |  |  |
| 100 | `MasterElm_ID` | INTEGER |  |  |  |
| 101 | `Flag_CtrlPrior` | SMALLINT |  |  |  |
| 102 | `Flag_Har` | SMALLINT |  |  |  |
| 103 | `qr` | FLOAT |  |  |  |
| 104 | `ql` | FLOAT |  |  |  |
| 105 | `HarImp_ID` | INTEGER |  |  |  |
| 106 | `HarVolt_ID` | INTEGER |  |  |  |
| 107 | `HarCur_ID` | INTEGER |  |  |  |
| 108 | `Flag_Reliability` | SMALLINT |  |  |  |
| 109 | `SupplyType_ID` | INTEGER |  |  |  |
| 110 | `Flag_ZU` | SMALLINT |  |  |  |
| 111 | `Flag_ZUP` | SMALLINT |  |  |  |
| 112 | `T_ZU` | FLOAT |  |  |  |
| 113 | `Flag_ShdU` | SMALLINT |  |  |  |
| 114 | `Flag_ShdP` | SMALLINT |  |  |  |
| 115 | `tShd` | FLOAT |  |  |  |
| 116 | `Flag_MaxMin` | SMALLINT |  |  |  |
| 117 | `Mpl_ID` | INTEGER |  |  |  |
| 118 | `Flag_LfCtrl` | SMALLINT |  |  |  |
| 119 | `Qctrl_Pstd` | FLOAT |  |  |  |
| 120 | `Ik2` | FLOAT |  |  |  |
| 121 | `Ik2max` | FLOAT |  |  |  |
| 122 | `Ik2min` | FLOAT |  |  |  |

Example row (non-empty fields only):

```
Element_ID=4, Variant_ID=1, Flag_Variant=1, Flag_Typ=2, Sk2=500.0, R_X=0.1, cact=1.0, Sk2max=500.0, R_Xmax=0.1, cmax=1.0, Sk2min=400.0, R_Xmin=0.1, cmin=1.0, Flag_Z0_Input=1, Flag_Lf=3, fP=1.0, fQ=1.0, cosphi=1.0, fS=1.0, fI=1.0, u=100.0, delta1=-30.0, delta2=-150.0, delta3=90.0, u1=100.0, u2=100.0, u3=100.0, ull=98.0, uul=103.0, cosphi_lim=0.85, Flag_ChkType=1, Qctrl_Pmin=0.5, Qctrl_Pmax=1.0, Qctrl_PF_Pmin=-0.95, Qctrl_PF_Pmax=0.95, Qctrl_Qmax=0.4843, Qctrl_cosphi_c=-0.95, Qctrl_cosphi=0.95, Qctrl_U1_c=97.0, Qctrl_U1=103.0, Qctrl_U2_c=92.0, Qctrl_U2=108.0, Flag_Har=1, qr=1.0, Flag_ZUP=3
```

